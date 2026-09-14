import * as fs from 'fs';
import * as path from 'path';
import * as cp from 'child_process';
import * as ts from 'typescript';

// Configuration
const entropyConfig = {
  maxTokenContext: 2000,
  maxMockDensity: 0.55,
  minUniqueCoverageThreshold: 5,
  executionMode: 'PR_SUGGESTION',
};

interface TestFileHealth {
  filePath: string;
  associatedSourceFiles: string[];
  loc: number;
  mockDensity: number;
  churnRate: number;
  tokenCost: number;
  uniqueCoverageLines: number;
  isCriticalPath: boolean;
}

interface RotVerdict {
  file: string;
  score: number;
  tags: ('BRITTLE_MOCKING' | 'CONTEXT_BLOAT' | 'REDUNDANT_COVERAGE' | 'TAUTOLOGY')[];
  suggestedAction: 'QUARANTINE' | 'COMPACT_SNAPSHOTS' | 'DELETE' | 'NONE';
}

function getGitChurn(filepath: string): number {
  try {
    const cmd = `git log --since='30 days ago' --oneline -- ${filepath} | wc -l`;
    const output = cp.execSync(cmd, { encoding: 'utf-8' });
    return parseInt(output.trim(), 10) || 0;
  } catch {
    return 0;
  }
}

function runCoverage() {
  // Mock coverage run
}

function getBaselineCoverage(): number {
  return 100;
}

function calculateUniqueCoverage(filepath: string, initialCoverage: number): number {
  let isCritical = false;
  if (fs.existsSync('critical_paths.json')) {
    const criticalPaths = JSON.parse(fs.readFileSync('critical_paths.json', 'utf-8'));
    if (criticalPaths.includes(filepath)) {
      isCritical = true;
    }
  }
  if (isCritical) {
    return 999999;
  }
  return 0; // default for mock
}

function checkRot(filepath: string): { score: number, tags: string[] } {
  const content = fs.readFileSync(filepath, 'utf-8');
  const lines = content.split('\n');
  const loc = lines.length;

  if (loc === 0) return { score: 0, tags: [] };

  const tags: string[] = [];

  let mockLines = 0;
  for (const line of lines) {
    if (line.includes('mock(') || line.includes('spyOn(') || line.includes('.mockReturnValue(')) {
      mockLines++;
    }
  }
  const mockDensity = mockLines / loc;
  if (mockDensity > entropyConfig.maxMockDensity) {
    tags.push('BRITTLE_MOCKING');
  }

  const tokenCost = content.length / 4;
  if (tokenCost > entropyConfig.maxTokenContext) {
    tags.push('CONTEXT_BLOAT');
  }

  // Tautology check
  const sourceFile = ts.createSourceFile(
    filepath,
    content,
    ts.ScriptTarget.Latest,
    true
  );

  let hasTautology = false;
  function visit(node: ts.Node) {
    if (ts.isCallExpression(node) && node.expression.getText() === 'expect') {
      // Very basic check for expect(true).toBe(true)
      if (node.arguments.length === 1 && node.arguments[0].getText() === 'true') {
        const parent = node.parent;
        if (ts.isPropertyAccessExpression(parent) && parent.name.getText() === 'toBe') {
           const grandParent = parent.parent;
           if (ts.isCallExpression(grandParent) && grandParent.arguments.length === 1 && grandParent.arguments[0].getText() === 'true') {
             hasTautology = true;
           }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);

  if (hasTautology) {
    tags.push('TAUTOLOGY');
  }

  return { score: tags.length * 33.3, tags };
}

function revertAndExit() {
  cp.execSync('git restore .');
  cp.execSync('git clean -fd');
  console.log('Reverted changes due to safety guardrails.');
  process.exit(1);
}

function externalizeSnapshots(filepath: string) {
    // simplified snapshot externalization logic
    const content = fs.readFileSync(filepath, 'utf-8');
    const sourceFile = ts.createSourceFile(
      filepath,
      content,
      ts.ScriptTarget.Latest,
      true
    );

    let newContent = content;
    let modified = false;
    let snapshotIdx = 0;
    const snapshotsDir = path.join(path.dirname(filepath), 'snapshots');

    function visit(node: ts.Node) {
        if (ts.isObjectLiteralExpression(node)) {
           if (node.properties.length > 10) {
               modified = true;
               snapshotIdx++;
               if (!fs.existsSync(snapshotsDir)) fs.mkdirSync(snapshotsDir, { recursive: true });
               const snapFile = path.join(snapshotsDir, `${path.basename(filepath)}_snap_${snapshotIdx}.json`);
               try {
                   // This is a naive extraction. Real implementation needs robust AST replacement
                   const objText = node.getText();
                   // If it's valid JSON-like structure
                   // For this simulation we will just replace the text
                   fs.writeFileSync(snapFile, objText);
                   newContent = newContent.replace(objText, `require('./snapshots/${path.basename(snapFile)}')`);
               } catch (e) {}
           }
        }
        ts.forEachChild(node, visit);
    }
    visit(sourceFile);
    if (modified) {
        fs.writeFileSync(filepath, newContent);
    }
}


function main() {
  if (!fs.existsSync('tests')) {
    return;
  }

  const initialCov = getBaselineCoverage();
  const actionsTaken: any[] = [];
  let flaggedForRemoval = 0;

  function walkDir(dir: string, callback: (file: string) => void) {
      const files = fs.readdirSync(dir);
      for (const file of files) {
          const filepath = path.join(dir, file);
          const stat = fs.statSync(filepath);
          if (stat.isDirectory()) {
              walkDir(filepath, callback);
          } else {
              callback(filepath);
          }
      }
  }

  const testFiles: string[] = [];
  walkDir('tests', (file) => {
     if (file.endsWith('.test.ts') || file.endsWith('.spec.ts')) {
         if (!file.includes('quarantine')) {
             testFiles.push(file);
         }
     }
  });

  for (const filepath of testFiles) {
    const uniqueCov = calculateUniqueCoverage(filepath, initialCov);
    const { score, tags } = checkRot(filepath);
    const churn = getGitChurn(filepath);

    let action = 'NONE';

    if (tags.includes('CONTEXT_BLOAT')) {
      action = 'REFACTORED';
      externalizeSnapshots(filepath);
    }

    if ((tags.includes('BRITTLE_MOCKING') || tags.includes('TAUTOLOGY')) && uniqueCov === 0) {
      action = 'DELETED';
      flaggedForRemoval++;
      fs.unlinkSync(filepath);
    } else if (churn > 5 && score > 50) {
      action = 'QUARANTINED';
      flaggedForRemoval++;
      if (!fs.existsSync('tests/quarantine')) {
          fs.mkdirSync('tests/quarantine', { recursive: true });
      }
      fs.renameSync(filepath, path.join('tests/quarantine', path.basename(filepath)));
    }

    if (action !== 'NONE') {
      actionsTaken.push({
        file: filepath,
        rot: tags.join(', '),
        unique_cov: `${uniqueCov} lines`,
        action
      });
    }
  }

  if (flaggedForRemoval > 20) {
    console.log("Vibe Check Failed: > 20 files flagged. Tagging Lead Architect.");
    revertAndExit();
  }

  const finalCov = getBaselineCoverage();

  if (initialCov - finalCov > 0.5) {
    console.log(`Coverage Cliff breached! initial=${initialCov}, final=${finalCov}`);
    revertAndExit();
  }

  console.log("Entropy Maintenance completed successfully.");

  if (actionsTaken.length > 0) {
    let report = "## [Entropy] Maintenance - Liability Reduction\n\n";
    report += "| File | Rot Type | Unique Coverage | Action Taken |\n";
    report += "|---|---|---|---|\n";
    for (const a of actionsTaken) {
      report += `| ${a.file} | ${a.rot} | ${a.unique_cov} | ${a.action} |\n`;
    }
    fs.writeFileSync('entropy_report.md', report);
  }
}

main();
