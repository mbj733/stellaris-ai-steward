// 选择命令链全景：执行器 FUN_14099cd60 本体 + 构造/消费函数调用者图
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin62 extends GhidraScript {
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
        decomp(0x14099cd60L, 160);
        decomp(0x1408e2270L, 90);
        long[] targets = new long[]{
            0x14099cd60L, 0x14099bfb0L, 0x14099d630L, 0x14099d6a0L, 0x14099ce90L,
            0x1408e9a10L, 0x1408e2270L, 0x1408e9aa0L, 0x14113ee90L
        };
        for (long t : targets) callers(t);
        println("==== done EvtWin62 ====");
    }
}
