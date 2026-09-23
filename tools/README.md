# Analysis tools

What produced `analysis/`. They read the app's armv7 Mach-O directly — it ships
unencrypted (`LC_ENCRYPTION_INFO cryptid = 0`), so no decryption step is needed.

They find the binary on their own: `analysis/bin/sixsense_armv7` (the thin slice)
first, then `game/sixsense` (the fat one from the bundle) — either works, the parser
takes both. `SIXTHSENSE_BINARY` overrides.

Needs `capstone`.

| | |
|---|---|
| `mb.py` | The Mach-O: fat header, load commands, sections, symbol table, indirect symbols and stubs, the dyld bind table (so external classes resolve to `_OBJC_CLASS_$_NSTimer` rather than `0`), plus `__objc_selrefs`, `__objc_classrefs`, `__objc_superrefs`, `__cfstring` and the ivar-offset globals. Imported by the rest. |
| `objc.py` | Walks `__objc_classlist` and writes `analysis/data/objc_classes.json`: 67 classes with their superclass, instance size, ivars (name, type, offset) and methods (name, type encoding, implementation address). Note the 32-bit `class_ro_t` has **no** `reserved` field — ten `uint32`s, not eleven. |
| `dz.py` | Raw Thumb-2 disassembly with annotations: `objc_msgSend` selectors resolved by tracking the `movw`/`movt`/`add rX, pc`/`ldr` PIC sequence, CFStrings, C strings, class refs, ivar-offset globals, and single/double literal-pool constants. |
| `dc.py` | The same, one level up: register shuffles collapsed, ivar loads and stores printed as `self->name`, calls printed as `r0 = [recv selector](args)`. This is what `analysis/disasm/dc_*.txt` is, and what the port was written from. |
| `pan_check.py` | Renders one source per lane through OpenAL Soft's loopback device with the game's own parameters and prints the left/right split. This is what established that the original is stereo panning, not binaural 3D. |
| `digest.py` | A terser call-sequence summary, useful for finding a method before reading it. |
| `rows.py` | A blind-mode screen's row table and its double-tap dispatch: pairs each `selectMenu = N` with the WAV that band plays, and decodes the `tbb` jump table in `tapCount` case by case. Every screen in this game has that shape, so this is what the shop and the inventory were read with. Standard library only. |
| `bands.py` | The same rows, sorted by where they sit on the screen: it pulls the `Y` bounds out of the float literal pool and pairs them with the `selectMenu` stores. Standard library only; shells out to `dz.py`. |

```bash
python objc.py                        # regenerate the class metadata
python dc.py Stage_1_E MainControl    # one method
python dc.py MonsterControl           # a whole class
python dz.py 0x3182c 0x322e0          # raw, by address
python dz.py "[Stage_1_E -MovingShot:]"
python rows.py StoreController        # the rows, and what a double tap does
python bands.py mainStoreController   # the rows, in screen order
```

Addresses are VM addresses in the thin armv7 slice, which is what every address in the
port's comments and in `docs/` refers to. `__TEXT` is mapped at `0x1000` from file
offset 0, so the byte at address `A` sits at offset `A - 0x1000` in
`analysis/bin/sixsense_armv7`. Reading the file at the address itself lands in
unrelated code.
