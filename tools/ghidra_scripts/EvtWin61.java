// 选择命令类指纹：扫描 vtable 0x1423ABDD8 / 0x1423ABE90 的全部引用者
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin61 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) f = getFunctionContaining(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 90, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            int n = Math.min(ls.length, cap);
            for (int i = 0; i < n; i++) println(ls[i]);
            if (ls.length > n) println("...(截断，全文 " + ls.length + " 行)");
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        LinkedHashSet<Long> fns = new LinkedHashSet<>();
        for (long vt : new long[]{0x1423ABDD8L, 0x1423ABE90L}) {
            println("==== refs to vtable 0x" + Long.toHexString(vt) + " ====");
            for (Reference r : getReferencesTo(toAddr(vt))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                        + " in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
                if (f != null) fns.add(f.getEntryPoint().getOffset());
            }
        }
        int n = 0;
        for (long a : fns) {
            if (a == 0x1408e2270L) continue;
            decomp(a, 140);
            if (++n >= 8) break;
        }
        println("==== done EvtWin61 ====");
    }
}
