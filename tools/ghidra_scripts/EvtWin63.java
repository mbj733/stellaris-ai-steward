// 解剖构造器调用者与 sel 的其它调用者：找 AI 自然选择路径
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin63 extends GhidraScript {
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
        decomp(0x14026c150L, 70);
        decomp(0x140bc4590L, 80);
        decomp(0x14127e340L, 80);
        decomp(0x14107c1b0L, 70);
        decomp(0x14137cfb0L, 70);
        callers(0x14026c150L);
        callers(0x140bc4590L);
        callers(0x14127e340L);
        callers(0x14107c1b0L);
        callers(0x14137cfb0L);
        println("==== done EvtWin63 ====");
    }
}
