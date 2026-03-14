export interface Reader {
  read(): string
}

export interface StreamReader extends Reader {
  stream(): string
}

export class FileReader implements StreamReader {
  read() {
    return "file"
  }

  stream() {
    return this.read()
  }
}

export class SpecialReader extends FileReader implements StreamReader {
  stream() {
    return super.stream()
  }
}
