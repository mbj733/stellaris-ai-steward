// 追执行器：FUN_141b2d780（命令投递）语义 + 分发器里 R14/目标对象来源 + 相关 xrefs
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class EvtWin38 extends GhidraScript {

    private void decomp(long addr, int cap) throws Exception {
        Function f = getFunctionAt(toAddr(addr));
        if (f == null) { println("(no function at 0x" + Long.toHexString(addr) + ")"); return; }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileResults res = di.decompileFunction(f, 60, monitor);
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(addr) + " (cap " + cap + ") ====");
        String[] ls = res.getDecompiledFunction().getC().split("\n");
        for (int i = 0; i < Math.min(ls.length, cap); i++) println("  " + ls[i]);
    }

    @Override
    public void run() throws Exception {
        decomp(0x141b2d780L, 160);
        println("==== xrefs to FUN_141b2d780 ====");
        for (Reference r : getReferencesTo(toAddr(0x141b2d780L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + "  " + r.getReferenceType() + "  in "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        decomp(0x14030e8c0L, 50);
        println("==== asm head of FUN_14107b1d0 (find R14/R15/R12 setup) ====");
        Instruction ins = getInstructionAt(toAddr(0x14107b1d0L));
        int n = 0;
        while (ins != null && n < 110) {
            String s = ins.toString();
            if (s.contains("R14") || s.contains("R15") || s.contains("R12") || n < 12) {
                println("  " + ins.getAddress() + "   " + s);
            }
            ins = ins.getNext();
            n++;
        }
        println("==== done ====");
    }
}
