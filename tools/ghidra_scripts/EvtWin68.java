// 派发执行 FUN_141a59590 + 效果体 FUN_140a22a10 + log88 里的 FUN_1408e1e30
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin68 extends GhidraScript {
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

    private void callers(long addr, int cap) {
        println("---- callers of 0x" + Long.toHexString(addr) + " ----");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(addr))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() + "@" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (++n >= cap) { println("  ...(截断)"); break; }
        }
        println("---- end callers 0x" + Long.toHexString(addr) + " ----");
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        decomp(0x141a59590L, 130);
        decomp(0x140a22a10L, 80);
        decomp(0x1408e1e30L, 60);
        callers(0x141a59590L, 40);
        println("==== done EvtWin68 ====");
    }
}
