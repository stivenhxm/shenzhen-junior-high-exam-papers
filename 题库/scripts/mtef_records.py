"""Read MathType 5 records for mtef-py 1.0.1's AST and TeX translator."""
from mtef_py.mtef import MTEF
from mtef_py import record as r


class EquationRecords(MTEF):
    """Keep fixed-width font-style records from consuming subsequent equation glyphs."""

    readers = {
        r.RecordType.LINE: (r.MtLine, MTEF.readLine),
        r.RecordType.CHAR: (r.MtChar, MTEF.readChar),
        r.RecordType.TMPL: (r.MtTmpl, MTEF.readTMPL),
        r.RecordType.PILE: (r.MtPile, MTEF.readPile),
        r.RecordType.MATRIX: (r.MtMatrix, MTEF.readMatrix),
        r.RecordType.EMBELL: (r.MtEmbellRd, MTEF.readEmbell),
        r.RecordType.EQN_PREFS: (r.MtEqnPrefs, MTEF.readEqnPrefs),
    }

    def unsigned(self):
        first = self.reader.read(1)[0]
        if first != 255:
            return first
        return int.from_bytes(self.reader.read(2), 'little')

    def readRecord(self):
        (self.mMtefVer, self.mPlatform, self.mProduct,
         self.mVersion, self.mVersionSub) = self.reader.read(5)
        if self.mMtefVer != 5:
            raise ValueError('Unsupported Equation Native version')
        self.mApplication, _ = self.readNullTerminatedString()
        self.mInline = self.reader.read(1)[0]
        self.Valid = True
        self.font_style_count = 0
        kind = r.RecordType
        while chunk := self.reader.read(1):
            record = chunk[0]
            value = None
            if record in self.readers:
                cls, read = self.readers[record]
                value = cls()
                read(self, value)
            elif record == kind.FONT_STYLE_DEF:
                # MTEF v5 stores an unsigned font-definition index and one
                # style byte. A nonzero style is not a NUL-terminated string.
                self.unsigned()
                self.reader.read(1)
                self.font_style_count += 1
                continue
            elif record == kind.FONT_DEF:
                value = r.MtfontDef()
                value.encDefIndex = self.unsigned()
                value.name, _ = self.readNullTerminatedString()
            elif record == kind.ENCODING_DEF:
                value, _ = self.readNullTerminatedString()
            elif record == kind.SIZE:
                self.reader.read(2)
                continue
            elif record == kind.COLOR:
                self.unsigned()
                continue
            elif record == kind.COLOR_DEF:
                self.readColorDef(r.MtColorDef())
                continue
            elif record >= kind.FUTURE:
                self.reader.seek(self.unsigned(), 1)
                continue
            elif record not in (kind.END, kind.FULL, kind.SUB, kind.SUB2, kind.SYM, kind.SUBSYM):
                raise ValueError(f'Unknown Equation Native record {record}')
            self.nodes.append(r.MtAST(record, value, None))
            if record == kind.MATRIX:
                # mtef-py's AST builder expects the two matrix line placeholders.
                self.nodes.extend(r.MtAST(kind.LINE, r.MtLine(), None) for _ in range(2))
