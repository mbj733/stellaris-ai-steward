// EvtWin31: 命令构造器 FUN_140a21fb0 + vtable 定位 + Execute
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class EvtWin31 extends GhidraScript {

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

    void dumpVtable(long vt, int n) {
        println("==== vtable @0x" + Long.toHexString(vt) + " ====");
        for (int k = 0; k < n; k++) {
            try {
                long fn = getLong(toAddr(vt + 8L * k));
                Function f = getFunctionContaining(toAddr(fn));
                println("  [" + k + "] 0x" + Long.toHexString(fn) + "  " + (f != null ? f.getName() : "?"));
            } catch (Exception e) {
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x140a21fb0L, 130);
        println("==== done ====");
    }
}
