// EvtWin16: resource 发放函数 FUN_140ee5320 + 数量解析
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin16 extends GhidraScript {

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

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() : "?"));
            if (++n >= 10) {
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x140ee5320L, 180);
        decompileFn(0x141b2d950L, 60);
        allRefs(0x140ee5320L, "grant fn");
        println("==== done ====");
    }
}
