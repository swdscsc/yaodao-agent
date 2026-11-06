import { AgentError } from "../runtime/errors";

export function encodeUTF8(value: string): Uint8Array {
  const byteLength = utf8ByteLength(value);
  const bytes = new Uint8Array(byteLength);
  let offset = 0;
  for (let index = 0; index < value.length; index += 1) {
    let codePoint = value.charCodeAt(index);
    if (codePoint >= 0xd800 && codePoint <= 0xdbff) {
      const low = value.charCodeAt(index + 1);
      if (low >= 0xdc00 && low <= 0xdfff) {
        codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + (low - 0xdc00);
        index += 1;
      }
    }
    if (codePoint <= 0x7f) {
      bytes[offset++] = codePoint;
    } else if (codePoint <= 0x7ff) {
      bytes[offset++] = 0xc0 | (codePoint >> 6);
      bytes[offset++] = 0x80 | (codePoint & 0x3f);
    } else if (codePoint <= 0xffff) {
      bytes[offset++] = 0xe0 | (codePoint >> 12);
      bytes[offset++] = 0x80 | ((codePoint >> 6) & 0x3f);
      bytes[offset++] = 0x80 | (codePoint & 0x3f);
    } else {
      bytes[offset++] = 0xf0 | (codePoint >> 18);
      bytes[offset++] = 0x80 | ((codePoint >> 12) & 0x3f);
      bytes[offset++] = 0x80 | ((codePoint >> 6) & 0x3f);
      bytes[offset++] = 0x80 | (codePoint & 0x3f);
    }
  }
  return bytes;
}

export function decodeUTF8(bytes: Uint8Array): string {
  if (typeof host !== "undefined" && typeof host.utf8Decode === "function") {
    try {
      return host.utf8Decode(bytes);
    } catch {
      throw utf8Error();
    }
  }
  const segments: string[] = [];
  const codeUnits: number[] = [];
  const flush = (): void => {
    if (codeUnits.length === 0) return;
    segments.push(String.fromCharCode(...codeUnits));
    codeUnits.length = 0;
  };
  for (let index = 0; index < bytes.length;) {
    const first = bytes[index];
    let length = 0;
    let codePoint = 0;
    if (first <= 0x7f) {
      length = 1;
      codePoint = first;
    } else if (first >= 0xc2 && first <= 0xdf) {
      length = 2;
      codePoint = first & 0x1f;
    } else if (first >= 0xe0 && first <= 0xef) {
      length = 3;
      codePoint = first & 0x0f;
    } else if (first >= 0xf0 && first <= 0xf4) {
      length = 4;
      codePoint = first & 0x07;
    } else {
      throw utf8Error();
    }
    if (index + length > bytes.length) throw utf8Error();
    for (let offset = 1; offset < length; offset += 1) {
      const continuation = bytes[index + offset];
      if ((continuation & 0xc0) !== 0x80) throw utf8Error();
      codePoint = (codePoint << 6) | (continuation & 0x3f);
    }
    const minimum = length === 1 ? 0 : length === 2 ? 0x80 : length === 3 ? 0x800 : 0x10000;
    if (codePoint < minimum
      || codePoint > 0x10ffff
      || codePoint >= 0xd800 && codePoint <= 0xdfff) {
      throw utf8Error();
    }
    if (codePoint <= 0xffff) {
      codeUnits.push(codePoint);
    } else {
      codeUnits.push(
        0xd800 + ((codePoint - 0x10000) >> 10),
        0xdc00 + ((codePoint - 0x10000) & 0x3ff),
      );
    }
    if (codeUnits.length >= 4_096) flush();
    index += length;
  }
  flush();
  return segments.join("");
}

export function utf8ByteLength(value: string): number {
  let byteLength = 0;
  for (let index = 0; index < value.length; index += 1) {
    let codePoint = value.charCodeAt(index);
    if (codePoint >= 0xd800 && codePoint <= 0xdbff) {
      const low = value.charCodeAt(index + 1);
      if (low >= 0xdc00 && low <= 0xdfff) {
        codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + (low - 0xdc00);
        index += 1;
      }
    }
    byteLength += codePoint <= 0x7f ? 1 : codePoint <= 0x7ff ? 2 : codePoint <= 0xffff ? 3 : 4;
  }
  return byteLength;
}

function utf8Error(): AgentError {
  return new AgentError("AGENT_MODEL_PROTOCOL_ERROR", "Invalid UTF-8 response", {
    phase: "transport",
  });
}
