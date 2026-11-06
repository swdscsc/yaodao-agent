export const MAX_CURRENT_USER_TEXT_BYTES = 32 << 10;

// stop_limit messages from the legacy agent may contain presentation HTML.
export function stripHTMLTags(text: string): string {
  return String(text || "").replace(/<[^>]{2,}>/g, "").trim();
}

export function utf8ByteLength(value: string): number {
  let length = 0;
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit <= 0x7f) {
      length += 1;
    } else if (codeUnit <= 0x7ff) {
      length += 2;
    } else if (
      codeUnit >= 0xd800
      && codeUnit <= 0xdbff
      && index + 1 < value.length
      && value.charCodeAt(index + 1) >= 0xdc00
      && value.charCodeAt(index + 1) <= 0xdfff
    ) {
      length += 4;
      index += 1;
    } else {
      length += 3;
    }
  }
  return length;
}

export function boundedCurrentUserText(value: string): string {
  return truncateUtf8(value.replace(/\u0000/g, ""), MAX_CURRENT_USER_TEXT_BYTES);
}

export function truncateUtf8(value: string, maximumBytes: number): string {
  const limit = Math.max(0, Math.floor(maximumBytes));
  let used = 0;
  for (let index = 0; index < value.length;) {
    const codeUnit = value.charCodeAt(index);
    let bytes = 3;
    let width = 1;
    if (codeUnit <= 0x7f) {
      bytes = 1;
    } else if (codeUnit <= 0x7ff) {
      bytes = 2;
    } else if (
      codeUnit >= 0xd800
      && codeUnit <= 0xdbff
      && index + 1 < value.length
      && value.charCodeAt(index + 1) >= 0xdc00
      && value.charCodeAt(index + 1) <= 0xdfff
    ) {
      bytes = 4;
      width = 2;
    }
    if (used + bytes > limit) return value.slice(0, index);
    used += bytes;
    index += width;
    if (index === value.length) return value;
    if (used === limit) return value.slice(0, index);
  }
  return value;
}

export function jsonUtf8ByteLength(value: unknown): number {
  return utf8ByteLength(JSON.stringify(value));
}
