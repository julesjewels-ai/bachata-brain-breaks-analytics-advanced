import * as fs from 'fs';
import * as path from 'path';
import lcovParse = require('lcov-parse');
import { globSync } from 'glob';
import Parser = require('tree-sitter');
import Python = require('tree-sitter-python');
import { Octokit } from '@octokit/rest';
import { execSync } from 'child_process';
import * as yaml from 'js-yaml';

// --- CONFIGURATION ---
const entropyConfig = {
  maxTokenContext: 2000,
  maxMockDensity: 0.55,
  minUniqueCoverageThreshold: 5,
  executionMode: 'PR_SUGGESTION', // 'PR_SUGGESTION' or 'REPORT_ONLY'
  coverageCliffThreshold: 0.005, // 0.5%
};

const ROOT_DIR = path.resolve(__dirname, '..');
const LCOV_FILE = path.join(ROOT_DIR, 'coverage', 'lcov.info');
const TESTS_DIR = path.join(ROOT_DIR, 'tests');
const SRC_DIR = path.join(ROOT_DIR, 'src');
const SNAPSHOT_DIR = path.join(TESTS_DIR, 'snapshots');
const QUARANTINE_DIR = path.join(TESTS_DIR, 'quarantine');
const CRITICAL_PATHS_FILE = path.join(ROOT_DIR, 'critical_paths.json');

// Ensure directories exist
if (!fs.existsSync(SNAPSHOT_DIR)) fs.mkdirSync(SNAPSHOT_DIR, { recursive: true });
if (!fs.existsSync(QUARANTINE_DIR)) fs.mkdirSync(QUARANTINE_DIR, { recursive: true });

// --- MODELS ---
interface TestFileHealth {
  filePath: string;
  associatedSourceFiles: string[];
  loc: number;
  mockDensity: number;
  churnRate: number;
  tokenCost: number;
  uniqueCoverageLines: number;
  isCriticalPath: boolean;
  rotVerdict?: RotVerdict;
}

interface RotVerdict {
  file: string;
  score: number;
  tags: ('BRITTLE_MOCKING' | 'CONTEXT_BLOAT' | 'REDUNDANT_COVERAGE' | 'TAUTOLOGY')[];
  suggestedAction: 'QUARANTINE' | 'COMPACT_SNAPSHOTS' | 'DELETE' | 'NONE';
}

// --- UTILS ---
function getFileChurn(filePath: string): number {
  try {
    const relPath = path.relative(ROOT_DIR, filePath);
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const cmd = `git log --since="${thirtyDaysAgo}" --oneline -- "${relPath}" | wc -l`;
    const result = execSync(cmd, { cwd: ROOT_DIR, encoding: 'utf-8' }).trim();
    return parseInt(result, 10);
  } catch (e) {
    return 0; // Fallback or if not tracked
  }
}

function calculateTokenCost(code: string): number {
  // Rough estimate: 1 token ~= 4 characters for English text/code
  return Math.ceil(code.length / 4);
}

function isCriticalPath(filePath: string): boolean {
  try {
    if (fs.existsSync(CRITICAL_PATHS_FILE)) {
      const criticalPaths = JSON.parse(fs.readFileSync(CRITICAL_PATHS_FILE, 'utf-8'));
      const relPath = path.relative(ROOT_DIR, filePath);
      return criticalPaths.includes(relPath);
    }
  } catch(e) {
    console.error("Error reading critical paths", e);
  }
  return false;
}

// --- PHASE 1: CARTOGRAPHY ---
async function parseLcov(filePath: string): Promise<any[]> {
  return new Promise((resolve, reject) => {
    lcovParse(filePath, (err, data) => {
      if (err) reject(err);
      else resolve(data || []);
    });
  });
}

function buildImportGraph(testFiles: string[]): Record<string, string[]> {
  const graph: Record<string, string[]> = {};
  for (const testFile of testFiles) {
    const content = fs.readFileSync(testFile, 'utf-8');
    const imports: string[] = [];

    // Rough regex for Python imports: from src.core... import ... OR import src.core...
    const fromImportRegex = /^from\s+([a-zA-Z0-9_\.]+)\s+import/gm;
    const importRegex = /^import\s+([a-zA-Z0-9_\.]+)/gm;

    let match;
    while ((match = fromImportRegex.exec(content)) !== null) {
      const modulePath = match[1].replace(/\./g, '/');
      const resolvedPath = path.join(ROOT_DIR, modulePath + '.py');
      if (fs.existsSync(resolvedPath) && resolvedPath.startsWith(SRC_DIR)) {
         imports.push(resolvedPath);
      }
    }
    while ((match = importRegex.exec(content)) !== null) {
      const modulePath = match[1].replace(/\./g, '/');
      const resolvedPath = path.join(ROOT_DIR, modulePath + '.py');
      if (fs.existsSync(resolvedPath) && resolvedPath.startsWith(SRC_DIR)) {
         imports.push(resolvedPath);
      }
    }
    graph[testFile] = [...new Set(imports)]; // Deduplicate
  }
  return graph;
}

async function calculateCoverageStats(lcovData: any[]): Promise<{ globalCoverage: number, fileCoverageMap: Record<string, Set<number>> }> {
    let totalLines = 0;
    let hitLines = 0;
    const fileCoverageMap: Record<string, Set<number>> = {};

    for (const fileData of lcovData) {
        const filePath = path.resolve(ROOT_DIR, fileData.file);
        if(!filePath.startsWith(SRC_DIR)) continue;

        const hitSet = new Set<number>();
        for (const lineData of fileData.lines.details) {
            totalLines++;
            if (lineData.hit > 0) {
                hitLines++;
                hitSet.add(lineData.line);
            }
        }
        fileCoverageMap[filePath] = hitSet;
    }

    const globalCoverage = totalLines === 0 ? 0 : hitLines / totalLines;
    return { globalCoverage, fileCoverageMap };
}

// Map uniquely covered lines to the test file that uniquely covers them
function mapUniqueCoverage(importGraph: Record<string, string[]>, fileCoverageMap: Record<string, Set<number>>): Record<string, number> {
    const uniqueCoverageCount: Record<string, number> = {};

    // Invert the import graph: srcFile -> list of testFiles that import it
    const invertedGraph: Record<string, string[]> = {};
    for (const [testFile, srcFiles] of Object.entries(importGraph)) {
        uniqueCoverageCount[testFile] = 0; // Initialize
        for (const srcFile of srcFiles) {
            if (!invertedGraph[srcFile]) invertedGraph[srcFile] = [];
            invertedGraph[srcFile].push(testFile);
        }
    }

    // Now calculate unique coverage
    for (const [srcFile, testFiles] of Object.entries(invertedGraph)) {
        // If a source file is only imported by exactly ONE test file
        // then ALL covered lines in that source file are "unique" to that test file.
        if (testFiles.length === 1) {
            const testFile = testFiles[0];
            const coveredLines = fileCoverageMap[srcFile];
            if (coveredLines) {
                 uniqueCoverageCount[testFile] += coveredLines.size;
            }
        }
        // If imported by multiple, we can't easily attribute specific lines to specific tests
        // statically without coverage trace per test. For this protocol, we assume 0 unique statically
        // if shared.
    }
    return uniqueCoverageCount;
}


// --- PHASE 2: ROT SCAN (AST ANALYSIS) ---
function analyzeAST(filePath: string, content: string): { mockLines: number, hasTautology: boolean, bloatCandidates: any[] } {
    const parser = new Parser();
    parser.setLanguage(Python);
    const tree = parser.parse(content);

    let mockLinesCount = 0;
    let hasTautology = false;
    const bloatCandidates: any[] = [];
    const mockLineNumbers = new Set<number>();

    function traverse(node: Parser.SyntaxNode) {
        // 1. Detect Mocks (mock, patch, MagicMock, return_value)
        if (node.type === 'call') {
            const funcNode = node.childForFieldName('function');
            if (funcNode) {
                const funcText = funcNode.text;
                if (funcText.includes('mock') || funcText.includes('patch') || funcText.includes('MagicMock')) {
                    mockLineNumbers.add(node.startPosition.row);
                }
            }
        } else if (node.type === 'attribute') {
            const attrNode = node.childForFieldName('attribute');
            if (attrNode && (attrNode.text === 'return_value' || attrNode.text === 'side_effect')) {
                mockLineNumbers.add(node.startPosition.row);
            }
        } else if (node.type === 'decorator') {
            if (node.text.includes('patch')) {
                 mockLineNumbers.add(node.startPosition.row);
            }
        }

        // 2. Detect Tautologies (assert True, assert 1 == 1)
        if (node.type === 'assert_statement') {
            const expr = node.children[1]; // The expression after 'assert'
            if (expr) {
                 if (expr.type === 'true' || expr.type === 'false' || expr.type === 'none') {
                     hasTautology = true;
                 }
                 if (expr.type === 'comparison_operator') {
                     const left = expr.children[0];
                     const op = expr.children[1];
                     const right = expr.children[2];
                     if (left && right && op && op.text === '==' && left.text === right.text) {
                         hasTautology = true;
                     }
                 }
            }
        }

        // 3. Detect Context Bloat (Large dicts/lists in assertions or assignments)
        if (node.type === 'dictionary' || node.type === 'list') {
            // Rough size check for bloat candidate
            if (node.endPosition.row - node.startPosition.row > 10 || node.text.length > 300) {
                 // Check if it's assigned to a variable or inside an assert
                 let parent = node.parent;
                 let isBloat = false;
                 while(parent) {
                     if (parent.type === 'assignment' || parent.type === 'assert_statement' || parent.type === 'call') {
                         isBloat = true;
                         break;
                     }
                     parent = parent.parent;
                 }
                 if (isBloat) {
                     bloatCandidates.push({
                         node,
                         text: node.text,
                         startRow: node.startPosition.row,
                         endRow: node.endPosition.row
                     });
                 }
            }
        }

        for (const child of node.children) {
            traverse(child);
        }
    }

    traverse(tree.rootNode);

    return {
        mockLines: mockLineNumbers.size,
        hasTautology,
        bloatCandidates
    };
}


async function analyzeFiles(testFiles: string[], uniqueCoverageCount: Record<string, number>, importGraph: Record<string, string[]>): Promise<TestFileHealth[]> {
    const healthData: TestFileHealth[] = [];

    for (const testFile of testFiles) {
        // Exclude quarantine
        if (testFile.includes('/quarantine/')) continue;

        const content = fs.readFileSync(testFile, 'utf-8');
        const loc = content.split('\n').length;
        const tokenCost = calculateTokenCost(content);
        const churnRate = getFileChurn(testFile);
        const isCrit = isCriticalPath(testFile);
        const uniqueLines = isCrit ? Infinity : (uniqueCoverageCount[testFile] || 0);

        const astData = analyzeAST(testFile, content);
        const mockDensity = loc > 0 ? (astData.mockLines / loc) : 0;

        const tags: ('BRITTLE_MOCKING' | 'CONTEXT_BLOAT' | 'REDUNDANT_COVERAGE' | 'TAUTOLOGY')[] = [];
        let score = 0;

        if (mockDensity > entropyConfig.maxMockDensity) {
            tags.push('BRITTLE_MOCKING');
            score += 40;
        }
        if (tokenCost > entropyConfig.maxTokenContext || astData.bloatCandidates.length > 0) {
            tags.push('CONTEXT_BLOAT');
            score += 30;
        }
        if (astData.hasTautology) {
            tags.push('TAUTOLOGY');
            score += 20;
        }
        if (uniqueLines === 0 && !isCrit) {
            tags.push('REDUNDANT_COVERAGE');
            score += 20;
        }

        let suggestedAction: 'QUARANTINE' | 'COMPACT_SNAPSHOTS' | 'DELETE' | 'NONE' = 'NONE';

        if ((tags.includes('BRITTLE_MOCKING') || tags.includes('TAUTOLOGY')) && uniqueLines === 0) {
            suggestedAction = 'DELETE';
        } else if (churnRate > 5 && score >= 40) {
            suggestedAction = 'QUARANTINE';
        } else if (tags.includes('CONTEXT_BLOAT')) {
            suggestedAction = 'COMPACT_SNAPSHOTS';
        }

        healthData.push({
            filePath: testFile,
            associatedSourceFiles: importGraph[testFile] || [],
            loc,
            mockDensity,
            churnRate,
            tokenCost,
            uniqueCoverageLines: uniqueLines,
            isCriticalPath: isCrit,
            rotVerdict: {
                file: path.basename(testFile),
                score,
                tags,
                suggestedAction
            }
        });
    }

    return healthData;
}

// --- PHASE 3: ACTION STRATEGIES ---
interface ActionLog {
    file: string;
    rotType: string;
    uniqueCoverage: number | string;
    actionTaken: string;
    rationale: string;
}

function applyStrategyA_CompactSnapshots(health: TestFileHealth): string | null {
    console.log(`[Strategy A] Compacting snapshots for ${health.filePath}`);
    const content = fs.readFileSync(health.filePath, 'utf-8');
    const astData = analyzeAST(health.filePath, content);

    if (astData.bloatCandidates.length === 0) return null;

    let modifiedContent = content;
    const baseName = path.basename(health.filePath, '.py');
    let snapshotCount = 0;

    // Sort reverse to replace without messing up positions
    astData.bloatCandidates.sort((a, b) => b.startRow - a.startRow);

    for (const candidate of astData.bloatCandidates) {
        const snapshotFile = path.join(SNAPSHOT_DIR, `${baseName}_snap_${snapshotCount}.json`);

        // Try to parse Python dict/list text to JSON if possible (rudimentary via Function/eval, or just save raw text)
        // For safety, we just save the raw Python string representation in a .txt or .py file if we can't easily JSONify Python code
        const snapshotDataFile = path.join(SNAPSHOT_DIR, `${baseName}_snap_${snapshotCount}.py`);

        fs.writeFileSync(snapshotDataFile, `data = ${candidate.text}`);

        // Replace in original file with an import or read
        const replacement = `_load_snapshot('${baseName}_snap_${snapshotCount}.py')`;
        modifiedContent = modifiedContent.substring(0, candidate.node.startIndex) + replacement + modifiedContent.substring(candidate.node.endIndex);
        snapshotCount++;
    }

    // Add helper function if missing
    if (snapshotCount > 0 && !modifiedContent.includes('def _load_snapshot')) {
        const helper = `\nimport os\ndef _load_snapshot(filename):\n    tests_dir = os.path.dirname(os.path.abspath(__file__))\n    while not os.path.exists(os.path.join(tests_dir, 'snapshots')) and os.path.basename(tests_dir) != 'tests':\n        tests_dir = os.path.dirname(tests_dir)\n    if not os.path.exists(os.path.join(tests_dir, 'snapshots')):\n        tests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests')\n    with open(os.path.join(tests_dir, 'snapshots', filename), 'r') as f:\n        loc = {}\n        exec(f.read(), globals(), loc)\n        return loc['data']\n\n`;
        // Insert after imports
        const lastImportIndex = modifiedContent.lastIndexOf('import ');
        const newlineAfterImport = modifiedContent.indexOf('\n', lastImportIndex);
        modifiedContent = modifiedContent.substring(0, newlineAfterImport + 1) + helper + modifiedContent.substring(newlineAfterImport + 1);
    }

    fs.writeFileSync(health.filePath, modifiedContent);
    return `Externalized ${snapshotCount} objects to snapshots`;
}

function applyStrategyB_Delete(health: TestFileHealth): string {
    console.log(`[Strategy B] Deleting liability ${health.filePath}`);
    fs.unlinkSync(health.filePath);
    return `Deleted. Liability > Value (0 Unique Cov)`;
}

function applyStrategyC_Quarantine(health: TestFileHealth): string {

    console.log(`[Strategy C] Quarantining high-churn file ${health.filePath}`);
    const dest = path.join(QUARANTINE_DIR, path.basename(health.filePath));
    fs.renameSync(health.filePath, dest);
    return `Moved to /quarantine (High Churn + Rot)`;
}


async function checkCoverageCliff(originalCoverage: number): Promise<boolean> {
    console.log(`Original Global Coverage: ${(originalCoverage * 100).toFixed(2)}%`);
    console.log(`Running test suite to check coverage cliff...`);

    try {
        execSync('./venv/bin/pytest --cov=src --cov-report=lcov:coverage/lcov.info', { cwd: ROOT_DIR, stdio: 'pipe' });
    } catch (e) {
        console.error("Tests failed after modifications. This is a cliff breach.");
        return true;
    }

    const newLcovData = await parseLcov(LCOV_FILE);
    const { globalCoverage: newCoverage } = await calculateCoverageStats(newLcovData);

    console.log(`New Global Coverage: ${(newCoverage * 100).toFixed(2)}%`);

    const drop = originalCoverage - newCoverage;
    console.log(`Coverage Drop: ${(drop * 100).toFixed(2)}%`);

    if (drop > entropyConfig.coverageCliffThreshold) {
        console.error(`COVERAGE CLIFF BREACHED! Drop is ${drop} > ${entropyConfig.coverageCliffThreshold}`);
        return true;
    }
    return false;
}

// --- MAIN PROTOCOL EXECUTION ---
async function runEntropy() {
    console.log("=== Initiating Entropy Protocol ===");

    // Ensure ignore files cover quarantine dir
    const cursorignore = path.join(ROOT_DIR, '.cursorignore');
    ['/tests/quarantine'].forEach(p => {
        if (fs.existsSync(cursorignore) && !fs.readFileSync(cursorignore, 'utf8').includes(p)) {
            fs.appendFileSync(cursorignore, '\n/tests/quarantine/\n');
        } else if (!fs.existsSync(cursorignore)) {
            fs.writeFileSync(cursorignore, '/tests/quarantine/\n');
        }
    });

    const testFiles = globSync('tests/**/*.py', { cwd: ROOT_DIR, absolute: true }).filter(f => !f.includes('__init__.py'));

    // 1. Cartography
    console.log("[Phase 1] Cartography & Coverage...");
    // Ensure initial coverage exists
    try {
        execSync('./venv/bin/pytest --cov=src --cov-report=lcov:coverage/lcov.info', { cwd: ROOT_DIR, stdio: 'pipe' });
    } catch (e) {
        console.log("Initial pytest failed. Cannot proceed with baseline.");
        process.exit(1);
    }

    const lcovData = await parseLcov(LCOV_FILE);
    const { globalCoverage: originalCoverage, fileCoverageMap } = await calculateCoverageStats(lcovData);
    const importGraph = buildImportGraph(testFiles);
    const uniqueCoverageCount = mapUniqueCoverage(importGraph, fileCoverageMap);

    // 2. Rot Scan
    console.log("[Phase 2] Rot Scan...");
    const healthData = await analyzeFiles(testFiles, uniqueCoverageCount, importGraph);

    // 3. Vibe Check
    const toModify = healthData.filter(h => h.rotVerdict?.suggestedAction !== 'NONE');
    if (toModify.length > 20) {
        console.error("VIBE CHECK FAILED: > 20 files flagged. Aborting and tagging Lead Architect.");
        process.exit(1);
    }

    // 4. Action Strategies
    console.log("[Phase 3] Action Strategy...");
    const actionLogs: ActionLog[] = [];

    for (const health of healthData) {
        const action = health.rotVerdict?.suggestedAction;
        if (!action || action === 'NONE') continue;

        let rationale = '';
        let taken = '';

        if (action === 'COMPACT_SNAPSHOTS') {
            const res = applyStrategyA_CompactSnapshots(health);
            if (res) {
                taken = 'REFACTORED';
                rationale = res;
            }
        } else if (action === 'DELETE') {
            rationale = applyStrategyB_Delete(health);
            taken = 'DELETED';
        } else if (action === 'QUARANTINE') {
            rationale = applyStrategyC_Quarantine(health);
            taken = 'QUARANTINED';
        }

        if (taken) {
            actionLogs.push({
                file: path.basename(health.filePath),
                rotType: health.rotVerdict?.tags.join(', ') || '',
                uniqueCoverage: health.uniqueCoverageLines === Infinity ? 'Infinite' : `${health.uniqueCoverageLines} lines`,
                actionTaken: taken,
                rationale: rationale
            });
        }
    }

    if (actionLogs.length === 0) {
        console.log("No actions required. Codebase is clean.");
        fs.writeFileSync(path.join(ROOT_DIR, 'entropy_report.md'), '## [Entropy] Maintenance - Liability Reduction\n\nNo actions required. Codebase is clean.\n');
        process.exit(0);
    }

    // 5. Coverage Cliff Verification
    console.log("[Guardrail] Checking Coverage Cliff...");
    const breached = await checkCoverageCliff(originalCoverage);
    if (breached) {
        console.log("Reverting changes due to coverage cliff/test failure...");
        execSync('git restore tests/', { cwd: ROOT_DIR });
        execSync('git clean -fd tests/', { cwd: ROOT_DIR });
        process.exit(1);
    }

    // 6. Cleanse (Output)
    console.log("[Phase 4] The Cleanse...");
    let report = `## [Entropy] Maintenance - Liability Reduction\n\n`;
    report += `| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n`;
    report += `|---|---|---|---|---|\n`;
    for (const log of actionLogs) {
         report += `| ${log.file} | ${log.rotType} | ${log.uniqueCoverage} | ${log.actionTaken} | ${log.rationale} |\n`;
    }

    fs.writeFileSync(path.join(ROOT_DIR, 'entropy_report.md'), report);
    console.log("Report generated at entropy_report.md");
    console.log("=== Entropy Protocol Complete ===");
}

runEntropy().catch(console.error);
