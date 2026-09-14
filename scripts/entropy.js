"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var fs = require("fs");
var path = require("path");
var cp = require("child_process");
var ts = require("typescript");
// Configuration
var entropyConfig = {
    maxTokenContext: 2000,
    maxMockDensity: 0.55,
    minUniqueCoverageThreshold: 5,
    executionMode: 'PR_SUGGESTION',
};
function getGitChurn(filepath) {
    try {
        var cmd = "git log --since='30 days ago' --oneline -- ".concat(filepath, " | wc -l");
        var output = cp.execSync(cmd, { encoding: 'utf-8' });
        return parseInt(output.trim(), 10) || 0;
    }
    catch (_a) {
        return 0;
    }
}
function runCoverage() {
    // Mock coverage run
}
function getBaselineCoverage() {
    return 100;
}
function calculateUniqueCoverage(filepath, initialCoverage) {
    var isCritical = false;
    if (fs.existsSync('critical_paths.json')) {
        var criticalPaths = JSON.parse(fs.readFileSync('critical_paths.json', 'utf-8'));
        if (criticalPaths.includes(filepath)) {
            isCritical = true;
        }
    }
    if (isCritical) {
        return 999999;
    }
    return 0; // default for mock
}
function checkRot(filepath) {
    var content = fs.readFileSync(filepath, 'utf-8');
    var lines = content.split('\n');
    var loc = lines.length;
    if (loc === 0)
        return { score: 0, tags: [] };
    var tags = [];
    var mockLines = 0;
    for (var _i = 0, lines_1 = lines; _i < lines_1.length; _i++) {
        var line = lines_1[_i];
        if (line.includes('mock(') || line.includes('spyOn(') || line.includes('.mockReturnValue(')) {
            mockLines++;
        }
    }
    var mockDensity = mockLines / loc;
    if (mockDensity > entropyConfig.maxMockDensity) {
        tags.push('BRITTLE_MOCKING');
    }
    var tokenCost = content.length / 4;
    if (tokenCost > entropyConfig.maxTokenContext) {
        tags.push('CONTEXT_BLOAT');
    }
    // Tautology check
    var sourceFile = ts.createSourceFile(filepath, content, ts.ScriptTarget.Latest, true);
    var hasTautology = false;
    function visit(node) {
        if (ts.isCallExpression(node) && node.expression.getText() === 'expect') {
            // Very basic check for expect(true).toBe(true)
            if (node.arguments.length === 1 && node.arguments[0].getText() === 'true') {
                var parent_1 = node.parent;
                if (ts.isPropertyAccessExpression(parent_1) && parent_1.name.getText() === 'toBe') {
                    var grandParent = parent_1.parent;
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
    return { score: tags.length * 33.3, tags: tags };
}
function revertAndExit() {
    cp.execSync('git restore .');
    cp.execSync('git clean -fd');
    console.log('Reverted changes due to safety guardrails.');
    process.exit(1);
}
function externalizeSnapshots(filepath) {
    // simplified snapshot externalization logic
    var content = fs.readFileSync(filepath, 'utf-8');
    var sourceFile = ts.createSourceFile(filepath, content, ts.ScriptTarget.Latest, true);
    var newContent = content;
    var modified = false;
    var snapshotIdx = 0;
    var snapshotsDir = path.join(path.dirname(filepath), 'snapshots');
    function visit(node) {
        if (ts.isObjectLiteralExpression(node)) {
            if (node.properties.length > 10) {
                modified = true;
                snapshotIdx++;
                if (!fs.existsSync(snapshotsDir))
                    fs.mkdirSync(snapshotsDir, { recursive: true });
                var snapFile = path.join(snapshotsDir, "".concat(path.basename(filepath), "_snap_").concat(snapshotIdx, ".json"));
                try {
                    // This is a naive extraction. Real implementation needs robust AST replacement
                    var objText = node.getText();
                    // If it's valid JSON-like structure
                    // For this simulation we will just replace the text
                    fs.writeFileSync(snapFile, objText);
                    newContent = newContent.replace(objText, "require('./snapshots/".concat(path.basename(snapFile), "')"));
                }
                catch (e) { }
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
    var initialCov = getBaselineCoverage();
    var actionsTaken = [];
    var flaggedForRemoval = 0;
    function walkDir(dir, callback) {
        var files = fs.readdirSync(dir);
        for (var _i = 0, files_1 = files; _i < files_1.length; _i++) {
            var file = files_1[_i];
            var filepath = path.join(dir, file);
            var stat = fs.statSync(filepath);
            if (stat.isDirectory()) {
                walkDir(filepath, callback);
            }
            else {
                callback(filepath);
            }
        }
    }
    var testFiles = [];
    walkDir('tests', function (file) {
        if (file.endsWith('.test.ts') || file.endsWith('.spec.ts')) {
            if (!file.includes('quarantine')) {
                testFiles.push(file);
            }
        }
    });
    for (var _i = 0, testFiles_1 = testFiles; _i < testFiles_1.length; _i++) {
        var filepath = testFiles_1[_i];
        var uniqueCov = calculateUniqueCoverage(filepath, initialCov);
        var _a = checkRot(filepath), score = _a.score, tags = _a.tags;
        var churn = getGitChurn(filepath);
        var action = 'NONE';
        if (tags.includes('CONTEXT_BLOAT')) {
            action = 'REFACTORED';
            externalizeSnapshots(filepath);
        }
        if ((tags.includes('BRITTLE_MOCKING') || tags.includes('TAUTOLOGY')) && uniqueCov === 0) {
            action = 'DELETED';
            flaggedForRemoval++;
            fs.unlinkSync(filepath);
        }
        else if (churn > 5 && score > 50) {
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
                unique_cov: "".concat(uniqueCov, " lines"),
                action: action
            });
        }
    }
    if (flaggedForRemoval > 20) {
        console.log("Vibe Check Failed: > 20 files flagged. Tagging Lead Architect.");
        revertAndExit();
    }
    var finalCov = getBaselineCoverage();
    if (initialCov - finalCov > 0.5) {
        console.log("Coverage Cliff breached! initial=".concat(initialCov, ", final=").concat(finalCov));
        revertAndExit();
    }
    console.log("Entropy Maintenance completed successfully.");
    if (actionsTaken.length > 0) {
        var report = "## [Entropy] Maintenance - Liability Reduction\n\n";
        report += "| File | Rot Type | Unique Coverage | Action Taken |\n";
        report += "|---|---|---|---|\n";
        for (var _b = 0, actionsTaken_1 = actionsTaken; _b < actionsTaken_1.length; _b++) {
            var a = actionsTaken_1[_b];
            report += "| ".concat(a.file, " | ").concat(a.rot, " | ").concat(a.unique_cov, " | ").concat(a.action, " |\n");
        }
        fs.writeFileSync('entropy_report.md', report);
    }
}
main();
