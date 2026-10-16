// EvtWin32: 调试菜单类 vtable(0x1436757e0) 的构造点与调用链
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;
import java.util.Set;

public class EvtWin32 extends GhidraScript {

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
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
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
        dumpVtable(0x1436757e0L, 12);
        println("==== refs to vtable 0x1436757e0（构造点） ====");
        Set<Long> fns = new LinkedHashSet<>();
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x1436757e0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (f != null) {
                fns.add(f.getEntryPoint().getOffset());
            }
            if (++n >= 12) {
                break;
            }
        }
        int d = 0;
        for (long fe : fns) {
            if (d++ >= 2) {
                break;
            }
            decompileFn(fe, 100);
        }
        println("==== done ====");
    }
}
