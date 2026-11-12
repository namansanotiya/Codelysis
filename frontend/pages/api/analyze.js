import { execFile } from 'child_process';
import path from 'path';
import fs from 'fs';

// In-memory cache to return instant results on repeat queries
const resultCache = new Map();

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { repo_path, github_url, pr_number, commit_sha, k = 2, diff_text } = req.body || {};

  const cacheKey = JSON.stringify({ repo_path, github_url, pr_number, commit_sha, k, diff_text: diff_text ? diff_text.slice(0, 200) : '' });
  if (resultCache.has(cacheKey)) {
    return res.status(200).json(resultCache.get(cacheKey));
  }

  const cwd = process.cwd();
  const rootDir = fs.existsSync(path.join(cwd, 'main.py'))
    ? cwd
    : path.resolve(cwd, '..');

  const venvPythonPosix = path.join(rootDir, 'venv', 'bin', 'python3');
  const venvPythonWin = path.join(rootDir, 'venv', 'Scripts', 'python.exe');
  let pythonBin = process.platform === 'win32' ? 'python' : 'python3';
  if (fs.existsSync(venvPythonWin)) {
    pythonBin = venvPythonWin;
  } else if (fs.existsSync(venvPythonPosix)) {
    pythonBin = venvPythonPosix;
  }
  const mainScript = path.join(rootDir, 'main.py');

  const args = [mainScript, '--json', '--hops', String(k)];
  if (github_url) {
    args.push('--github', github_url);
  } else if (repo_path) {
    const resolvedPath = path.isAbsolute(repo_path) ? repo_path : path.join(rootDir, repo_path);
    args.push('--repo', resolvedPath);
  } else {
    args.push('--repo', path.join(rootDir, 'sample_repo'));
  }

  if (pr_number) args.push('--pr', String(pr_number));
  if (commit_sha) args.push('--commit', String(commit_sha));
  if (diff_text) args.push('--diff', diff_text);

  return new Promise((resolve) => {
    // Generous 3-minute timeout so large multi-language repos (like Chess) complete easily
    execFile(
      pythonBin,
      args,
      {
        cwd: rootDir,
        encoding: 'utf-8',
        maxBuffer: 50 * 1024 * 1024,
        timeout: 300000
      },
      (err, stdout, stderr) => {
        if (err) {
          if (err.killed || err.signal === 'SIGTERM') {
            res.status(504).json({
              error: 'Analysis timed out after 3 minutes. Try setting depth k=1 for a faster scan on large repositories.'
            });
            return resolve();
          }
          res.status(500).json({
            error: `Execution failed: ${err.message}`,
            stderr: stderr || ''
          });
          return resolve();
        }

        try {
          const jsonStart = stdout.indexOf('{');
          const jsonEnd = stdout.lastIndexOf('}');
          if (jsonStart !== -1 && jsonEnd !== -1) {
            const jsonStr = stdout.substring(jsonStart, jsonEnd + 1);
            const parsed = JSON.parse(jsonStr);
            resultCache.set(cacheKey, parsed);
            res.status(200).json(parsed);
            return resolve();
          }
          res.status(500).json({ error: 'Could not find JSON in Python output', raw: stdout });
          return resolve();
        } catch (parseErr) {
          res.status(500).json({ error: `JSON Parse error: ${parseErr.message}`, raw: stdout });
          return resolve();
        }
      }
    );
  });
}
