// 找真正的"选项点击执行链"：option_click 引用函数 + 窗口 Setup（挂按钮动作）+ 分发器全文
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin39 extends GhidraScript {

    private void decomp(long addr, int cap) throws Exception {
        Function f = getFunctionAt(toAddr(addr));
        if (f == null) { println("(no function at 0x" + Long.toHexString(addr) + ")"); return; }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileResults res = di.decompileFunction(f, 90, monitor);
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(addr) + " (cap " + cap + ") ====");
        String[] ls = res.getDecompiledFunction().getC().split("\n");
        for (int i = 0; i < Math.min(ls.length, cap); i++) println("  " + ls[i]);
    }

    @Override
    public void run() throws Exception {
        decomp(0x1412913a0L, 220);                       // "option_click" 引用函数
        println("==== xrefs to FUN_1412913a0 ====");
        for (Reference r : getReferencesTo(toAddr(0x1412913a0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + "  " + r.getReferenceType() + "  in "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        decomp(0x14107a180L, 300);                       // 窗口 Setup 系（含 event_option_button）
        decomp(0x1410793a0L, 160);                       // 窗口 Setup 主
        println("==== done ====");
    }
}
