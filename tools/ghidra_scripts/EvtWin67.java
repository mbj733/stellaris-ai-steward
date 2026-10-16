// 提交器/热函数解剖：FUN_1405f88a0(提交) FUN_1408e6b70(疑似执行) FUN_140bc4590(469次热) FUN_140a23740(选项校验/执行)
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin67 extends GhidraScript {
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

    private void callers(long addr) {
        println("---- callers of 0x" + Long.toHexString(addr) + " ----");
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        for (Reference r : getReferencesTo(toAddr(addr))) {
            Function f = getFunctionContaining(r.getFromAddress());
            String s = "  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() + "@" + Long.toHexString(f.getEntryPoint().getOffset()) : "?");
            if (seen.add(s)) println(s);
        }
        println("---- end callers 0x" + Long.toHexString(addr) + " ----");
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        decomp(0x1405f88a0L, 110);
        decomp(0x1408e6b70L, 90);
        decomp(0x140bc4590L, 90);
        decomp(0x140a23740L, 90);
        callers(0x1405f88a0L);
        callers(0x1408e6b70L);
        callers(0x140bc4590L);
        println("==== done EvtWin67 ====");
    }
}
