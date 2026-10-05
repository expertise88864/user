// Git text checkouts may use CRLF. Preserve every other artifact byte.
function gitTextBytes(value) {
  return Buffer.from(value).filter((byte, index, bytes) => byte !== 13 || bytes[index + 1] !== 10);
}

export function sameGitTextArtifact(actual, generated) {
  return gitTextBytes(actual).equals(gitTextBytes(generated));
}
