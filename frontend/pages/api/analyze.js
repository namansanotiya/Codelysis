import { execFileSync } from 'child_process';
import path from 'path';
import fs from 'fs';

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { repo_path, github_url, pr_number, commit_sha, k = 2, diff_text } = req.body || {};

  const cwd = process.cwd();
  const rootDir = fs.existsSync(path.join(cwd, 'main.py'))
    ? cwd
    : path.resolve(cwd, '..');

  const pythonBin = path.join(rootDir, 'venv', 'bin', 'python3');
  const mainScript = path.join(rootDir, 'main.py');

  const args = [mainScript, '--json', '--hops', String(k)];
  if (github_url) {
    args.push('--github', github_url);
  } else if (repo_path) {
    // If relative path like 'sample_repo', resolve relative to rootDir
    const resolvedPath = path.isAbsolute(repo_path) ? repo_path : path.join(rootDir, repo_path);
    args.push('--repo', resolvedPath);
  } else {
    args.push('--repo', path.join(rootDir, 'sample_repo'));
  }

  if (pr_number) {
    args.push('--pr', String(pr_number));
  }
  if (commit_sha) {
    args.push('--commit', String(commit_sha));
  }
  if (diff_text) {
    args.push('--diff', diff_text);
  }

  try {
    const stdout = execFileSync(pythonBin, args, {
      cwd: rootDir,
      encoding: 'utf-8',
      maxBuffer: 20 * 1024 * 1024,
      timeout: 30000
    });

    const jsonStart = stdout.indexOf('{');
    const jsonEnd = stdout.lastIndexOf('}');
    if (jsonStart !== -1 && jsonEnd !== -1) {
      const jsonStr = stdout.substring(jsonStart, jsonEnd + 1);
      const parsed = JSON.parse(jsonStr);
      return res.status(200).json(parsed);
    }
    return res.status(500).json({ error: 'Could not find JSON in Python output', raw: stdout });
  } catch (err) {
    return res.status(500).json({
      error: `Execution failed: ${err.message}`,
      stderr: err.stderr ? err.stderr.toString() : ''
    });
  }
}
