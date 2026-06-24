let _pendingFile: File | null = null;
let _pendingUrl: string | null = null;

export function setSearchImage(file: File, objectUrl: string) {
  _pendingFile = file;
  _pendingUrl = objectUrl;
}

export function getSearchImage(imageUrl: string): File | null {
  if (_pendingFile && _pendingUrl === imageUrl) {
    return _pendingFile;
  }
  return null;
}

export function clearSearchImage() {
  _pendingFile = null;
  _pendingUrl = null;
}
