// 终局锚点：FUN_1408e2270 = 事件选项应用函数
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin57 extends GhidraScript {
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
        println("==== refs to FUN_1408e2270 ====");
        java.util.LinkedHashSet<Long> callers = new java.util.LinkedHashSet<>();
        try {
            for (Reference r : getReferencesTo(toAddr(0x1408e2270L))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                        + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
                if (f != null) callers.add(f.getEntryPoint().getOffset());
            }
        } catch (Exception e) { println("  fail: " + e); }
        decomp(0x1408e2270L, 400);
        decomp(0x1408e1e30L, 150);
        int n = 0;
        for (long c : callers) {
            if (c == 0x1408e2270L) continue;
            decomp(c, 130);
            if (++n >= 8) break;
        }
        println("==== done EvtWin57 ====");
    }
}
