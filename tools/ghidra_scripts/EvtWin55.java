// 点击链上游与兜底：调用者/兜底处理器/selected_event_option 使用者
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin55 extends GhidraScript {
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

    private void xrefs(long addr, String label) {
        println("==== refs to " + label + " ====");
        try {
            for (Reference r : getReferencesTo(toAddr(addr))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                        + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        } catch (Exception e) { println("  fail: " + e); }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        xrefs(0x1414580c0L, "FUN_1414580c0(兜底处理器)");
        xrefs(0x14137c560L, "FUN_14137c560");
        xrefs(0x141378c30L, "FUN_141378c30");
        xrefs(0x14107c1b0L, "FUN_14107c1b0(selected_event_option 使用者)");
        decomp(0x14137c560L, 400);
        decomp(0x141378c30L, 300);
        decomp(0x1414580c0L, 300);
        decomp(0x14107c1b0L, 250);
        decomp(0x1408e1e30L, 120);
        decomp(0x14107d850L, 100);
        println("==== 包含 0x141013d37 的函数 ====");
        Function f = getFunctionContaining(toAddr(0x141013d37L));
        if (f != null) { println("  " + f.getName() + "@" + f.getEntryPoint()); decomp(f.getEntryPoint().getOffset(), 250); }
        println("==== done EvtWin55 ====");
    }
}
