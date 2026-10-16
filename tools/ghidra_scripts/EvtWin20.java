// EvtWin20: 回调写入者 FUN_140a32570 + 附近 PTR
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin20 extends GhidraScript {

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

    void dumpPtr(long ptr) {
        println("==== PTR @0x" + Long.toHexString(ptr) + " ====");
        for (int i = 0; i < 6; i++) {
            try {
                long v = getLong(toAddr(ptr + 8L * i));
                Function f = getFunctionContaining(toAddr(v));
                println(String.format("  [%d] 0x%x %s", i, v, f != null ? f.getName() : ""));
            } catch (Exception e) {
                break;
            }
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() : "?"));
            if (++n >= 15) {
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x140a32570L, 160);
        dumpPtr(0x1422fe568L);
        allRefs(0x140a32570L, "delegate writer");
        println("==== done ====");
    }
}
