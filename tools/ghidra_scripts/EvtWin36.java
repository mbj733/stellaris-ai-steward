// EvtWin36: 识别"命令上下文"对象类——FUN_141378c30/FUN_14137c560 所在 vtable 与邻近类名
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin36 extends GhidraScript {

    String readCStr(long va, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) {
                    break;
                }
                if (b < 32 || b > 126) {
                    return null;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
            return null;
        }
        return sb.length() >= 4 ? sb.toString() : null;
    }

    void refs(long va, String label) {
        println("==== refs to " + label + " ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            if (r.getReferenceType().isCall()) {
                continue;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + (f != null ? " in " + f.getName() : ""));
            if (++n >= 10) {
                break;
            }
        }
    }

    void dumpStrings(long start, long end, String tag) {
        println("==== strings via ptrs " + tag + " ====");
        int n = 0;
        for (long a = start; a < end; a += 8) {
            try {
                long v = getLong(toAddr(a));
                if (v > 0x140000000L && v < 0x150000000L) {
                    String s = readCStr(v, 90);
                    if (s != null) {
                        println("  @0x" + Long.toHexString(a) + " -> \"" + s + "\"");
                        if (++n >= 40) {
                            return;
                        }
                    }
                }
            } catch (Exception e) {
            }
        }
    }

    @Override
    public void run() throws Exception {
        refs(0x141378c30L, "FUN_141378c30");
        refs(0x14137c560L, "FUN_14137c560");
        dumpStrings(0x142439040L, 0x142439400L, "table2 area");
        dumpStrings(0x1424620C0L, 0x142462380L, "table3 area");
        println("==== done ====");
    }
}
