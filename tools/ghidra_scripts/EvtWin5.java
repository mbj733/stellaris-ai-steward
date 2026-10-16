// EvtWin5: 回调对象构造器 FUN_1407b5a10 全文 + PTR_FUN_142560770 + 菜单定义表
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin5 extends GhidraScript {

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
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void dumpTable(long start, int words) {
        println("==== table @0x" + Long.toHexString(start) + " (" + words + " qwords) ====");
        for (int i = 0; i < words; i++) {
            long a = start + 8L * i;
            try {
                long v = getLong(toAddr(a));
                String extra = "";
                if (v >= 0x140000000L && v < 0x150000000L) {
                    Function f = getFunctionContaining(toAddr(v));
                    if (f != null && f.getEntryPoint().getOffset() == v) {
                        extra = "  -> " + f.getName();
                    } else if (f != null) {
                        extra = "  -> inside " + f.getName() + " (+0x" + Long.toHexString(v - f.getEntryPoint().getOffset()) + ")";
                    } else {
                        extra = "  -> (data?)";
                    }
                }
                println(String.format("  @0x%x : 0x%x%s", a, v, extra));
            } catch (Exception e) {
                println("  @0x" + Long.toHexString(a) + " : (unreadable)");
            }
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " ====");
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x1407b5a10L, 330);
        dumpTable(0x142560770L, 6);
        dumpTable(0x1423a94c0L, 10);
        dumpTable(0x1423a9d60L, 10);
        allRefs(0x142560770L, "PTR_FUN_142560770 vtable");
        decompileFn(0x1410793a0L, 420);
        println("==== done ====");
    }
}
