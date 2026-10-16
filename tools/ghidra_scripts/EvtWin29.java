// EvtWin29: FUN_1408e5d20 全文 + 命令名表解析
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class EvtWin29 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 150, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            }
            dec.dispose();
        } catch (Exception e) {
        }
    }

    String readCStr(long va, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) {
                    break;
                }
                if (b < 32 || b > 126) {
                    break;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
        }
        return sb.toString();
    }

    void dumpTable(long start, int words) {
        println("==== table @0x" + Long.toHexString(start) + " ====");
        for (int i = 0; i < words; i++) {
            long a = start + 8L * i;
            try {
                long v = getLong(toAddr(a));
                String extra = "";
                if (v >= 0x140000000L && v < 0x150000000L) {
                    Function f = getFunctionContaining(toAddr(v));
                    if (f != null && f.getEntryPoint().getOffset() == v) {
                        extra = "  -> " + f.getName();
                    } else {
                        String s = readCStr(v, 60);
                        if (s.length() >= 3) {
                            extra = "  -> \"" + s + "\"";
                        } else if (f != null) {
                            extra = "  -> inside " + f.getName();
                        } else {
                            extra = "  -> (data)";
                        }
                    }
                }
                println(String.format("  @0x%x : 0x%x%s", a, v, extra));
            } catch (Exception e) {
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x1408e5d20L, 160);
        dumpTable(0x142403540L, 12);
        dumpTable(0x142439180L, 10);
        dumpTable(0x142462230L, 10);
        println("==== done ====");
    }
}
