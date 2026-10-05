import {build, transform} from 'esbuild';
import {readFile, writeFile, readdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {sameGitTextArtifact} from './_editor_artifact_text.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(root, 'admin/word-model.bundle.js');
const result = await build({
  absWorkingDir: root, entryPoints: ['admin/word-model.js'], outfile: output,
  bundle: true, format: 'iife', target: 'es2022', minify: true,
  // Escape parser sentinel characters in source without changing string values;
  // literal U+FFFD would otherwise fail the repository's text-integrity gate.
  legalComments: 'eof', charset: 'ascii', write: false, metafile: true
});
const styles = await Promise.all(['node_modules/prosemirror-view/style/prosemirror.css',
  'node_modules/prosemirror-tables/style/tables.css', 'admin/word-editor.css'].map(file=>readFile(path.join(root,file),'utf8')));
const css = await transform(styles.join('\n'),{loader:'css',minify:true,charset:'utf8'});
// Retain the licenses of every dependency actually included in the bundle.
const packageNames = [...new Set(Object.keys(result.metafile.inputs).filter(file=>file.startsWith('node_modules/')).map(file=>{
  const parts=file.slice('node_modules/'.length).split('/');return parts[0].startsWith('@')?parts.slice(0,2).join('/'):parts[0];
}))].sort();
const notices = [];
for (const name of packageNames) {
  const directory=path.join(root,'node_modules',name), pkg=JSON.parse(await readFile(path.join(directory,'package.json'),'utf8'));
  const candidates=(await readdir(directory)).filter(file=>/^(?:licen[sc]e)(?:\.(?:txt|md))?$/i.test(file)).sort();
  if(!candidates.length)throw Error('Missing bundled dependency license: '+name);
  notices.push(name+' '+pkg.version+'\n'+await readFile(path.join(directory,candidates[0]),'utf8'));
}
const outputs = new Map([[output,result.outputFiles[0].contents],
  [path.join(root,'admin/word-editor.bundle.css'),Buffer.from(css.code)],
  [path.join(root,'admin/word-model.LICENSE.txt'),Buffer.from(notices.join('\n\n---\n\n').trimEnd()+'\n')]]);
if (process.argv.slice(2).includes('--check')) {
  for(const [file,bytes] of outputs) {
    let actual;
    try { actual = await readFile(file); } catch (_) { throw Error('Word editor artifact is missing: '+path.basename(file)); }
    if (!sameGitTextArtifact(actual, bytes)) throw Error('Word editor artifact is stale: '+path.basename(file));
  }
  console.log('Word editor JS/CSS/licenses match pinned source and dependencies');
} else {
  for(const [file,bytes] of outputs)await writeFile(file,bytes);
  console.log(`Word editor JS/CSS/licenses generated: ${result.outputFiles[0].contents.length} JS bytes`);
}
