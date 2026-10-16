// 大合集：点击链候选函数的完整反编译（一次性抓全，后续用 grep 读）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class EvtWin49 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) { println("(no function at 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 90, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(addr) + " cap=" + cap + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, cap); i++) println(ls[i]);
        } catch (Exception e) {
            println("decomp fail 0x" + Long.toHexString(addr) + ": " + e);
        }
    }

    private void xrefs(long addr) {
        println("==== xrefs to 0x" + Long.toHexString(addr) + " ====");
        for (Reference r : getReferencesTo(toAddr(addr))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
    }

    private void asm(long center, int back, int fwd) {
        println("==== asm @0x" + Long.toHexString(center) + " ====");
        Address start = toAddr(center - back);
        Instruction ins = getInstructionAt(start);
        if (ins == null) ins = getInstructionAfter(start);
        int n = 0;
        while (ins != null && n < 80) {
            String tag = ins.getAddress().getOffset() == center ? "   <<<<<" : "";
            println("  " + ins.getAddress() + "   " + ins + tag);
            if (ins.getAddress().getOffset() > center + fwd) break;
            ins = ins.getNext();
            n++;
        }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        decomp(0x14107b1d0L, 700);      // 窗口命令 槽0（长文）
        decomp(0x141378c30L, 400);      // 调用者1
        decomp(0x14137c560L, 400);      // 调用者2
        asm(0x141378c5bL, 0x30, 0x20);  // 调用点 asm
        asm(0x14137ca64L, 0x30, 0x20);
        decomp(0x141589a60L, 250);      // coop by_other 处理
        decomp(0x1403f5de0L, 400);      // 事件内核（AI 选择路径）
        decomp(0x140d608d0L, 60);
        decomp(0x1407bf7b0L, 60);
        decomp(0x1407b4d40L, 60);
        decomp(0x14128fa00L, 70);       // option_click 遥测包装们
        decomp(0x141291ad0L, 70);
        decomp(0x141291c80L, 60);
        decomp(0x141291ce0L, 60);
        xrefs(0x14128fa00L);
        xrefs(0x141291ad0L);
        xrefs(0x141291c80L);
        xrefs(0x141291ce0L);
        decomp(0x14107a640L, 130);      // 窗口槽4
        decomp(0x14107a730L, 130);      // 窗口槽6
        println("==== done ====");
    }
}
