// EvtWin21: 调试菜单入口——谁消费菜单表 + 区域字符串（找窗口名）
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin21 extends GhidraScript {

    String s(long va) {
        try {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 60; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) break;
                if (b < 32 || b > 126) return null;
                sb.append((char) b);
            }
            return sb.length() >= 4 ? sb.toString() : null;
        } catch (Exception e) {
            return null;
        }
    }

    void refs(long va, String tag) {
        println("==== refs to " + tag + " 0x" + Long.toHexString(va) + " ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (++n >= 12) {
                println("  ...");
                break;
            }
        }
    }

    void dumpStrings(long start, long end) {
        println("==== strings via pointers 0x" + Long.toHexString(start) + "..0x" + Long.toHexString(end) + " ====");
        int n = 0;
        for (long a = start; a < end; a += 8) {
            try {
                long v = getLong(toAddr(a));
                if (v >= 0x140000000L && v < 0x150000000L) {
                    String str = s(v);
                    if (str != null) {
                        println("  @0x" + Long.toHexString(a) + " -> \"" + str + "\"");
                        if (++n >= 60) {
                            break;
                        }
                    }
                }
            } catch (Exception e) {
            }
        }
    }

    @Override
    public void run() throws Exception {
        refs(0x1423a9d60L, "menu table B(9d60)");
        refs(0x1423a94c0L, "menu table A(94c0)");
        dumpStrings(0x1423a9800L, 0x1423aa400L);
        println("==== done ====");
    }
}
