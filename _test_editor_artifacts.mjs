import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {sameGitTextArtifact} from './_editor_artifact_text.mjs';

for (const file of ['admin/word-model.bundle.js', 'admin/word-editor.bundle.css', 'admin/word-model.LICENSE.txt']) {
  test('Windows checkout preserves the pinned artifact contract: '+file, async () => {
    const original = await readFile(file);
    const lf = Buffer.from(original.toString('utf8').replace(/\r\n/g, '\n'));
    const crlf = Buffer.from(lf.toString('utf8').replace(/\n/g, '\r\n'));
    assert.equal(sameGitTextArtifact(lf, crlf), true);
    assert.equal(sameGitTextArtifact(crlf, lf), true);
    const changed = Buffer.from(crlf); changed[0] ^= 1;
    assert.equal(sameGitTextArtifact(changed, lf), false, 'changed code/license bytes must still fail');
    assert.equal(sameGitTextArtifact(lf.subarray(0, lf.length - 1), lf), false, 'truncation must still fail');
  });
}

test('artifact checking retains bare CR, NUL and invalid UTF-8 bytes', () => {
  for (const bytes of [Buffer.from([13]), Buffer.from([0]), Buffer.from([255])]) {
    assert.equal(sameGitTextArtifact(bytes, Buffer.alloc(0)), false);
    assert.equal(sameGitTextArtifact(bytes, Buffer.from([239, 191, 189])), false);
  }
});
