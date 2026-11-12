import { expect, type BrowserContext } from "@playwright/test";

export interface RecordedRequest {
  method: string;
  url: string;
}

function globToRegExp(glob: string): RegExp {
  let source = "";
  for (let index = 0; index < glob.length; index += 1) {
    const character = glob[index] ?? "";
    if (character === "*" && glob[index + 1] === "*") {
      source += ".*";
      index += 1;
    } else if (character === "*") {
      source += "[^/]*";
    } else {
      source += character.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(`^${source}$`);
}

/** Records every request made by the watched browser contexts for glob assertions. */
export class RequestRecorder {
  private readonly records: RecordedRequest[] = [];

  watch(context: BrowserContext): void {
    context.on("request", (request) => {
      this.records.push({ method: request.method(), url: request.url() });
    });
  }

  matching(glob: string): RecordedRequest[] {
    const pattern = globToRegExp(glob);
    return this.records.filter((record) => pattern.test(record.url));
  }

  expectNone(glob: string): void {
    expect(this.matching(glob), `requests matching ${glob}`).toEqual([]);
  }

  expectSome(glob: string): void {
    expect(this.matching(glob).length, `requests matching ${glob}`).toBeGreaterThan(0);
  }
}
