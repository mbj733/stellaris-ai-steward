// 点击链线索：option_click 遥测包装函数 + 窗口槽函数 FUN_14107a640/14107a730
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin48 extends GhidraScript {
    private void decomp(long addr, int cap) throws Exception {
        Function f = getFunctionAt(toAddr(addr));
        if (f == null) { println("(no function at 0x" + Long.toHexString(addr) + ")"); return; }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileResults res = di.decompileFunction(f, 60, monitor);
        println("==== " + f.getName() + " @0x" + Long.toHexString(addr) + " ====");
        String[] ls = res.getDecompiledFunction().getC().split("\n");
        for (int i = 0; i < Math.min(ls.length, cap); i++) println(ls[i]);
    }

    private void xrefs(long addr) {
        println("==== xrefs to 0x" + Long.toHexString(addr) + " ====");
        for (Reference r : getReferencesTo(toAddr(addr))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
    }

    @Override
    public void run() throws Exception {
        decomp(0x14128fa00L, 70);
        decomp(0x141291ad0L, 70);
        decomp(0x141291c80L, 60);
        decomp(0x141291ce0L, 60);
        xrefs(0x14128fa00L);
        xrefs(0x141291ad0L);
        xrefs(0x141291c80L);
        xrefs(0x141291ce0L);
        decomp(0x14107a640L, 110);
        decomp(0x14107a730L, 110);
        println("==== done ====");
    }
}
