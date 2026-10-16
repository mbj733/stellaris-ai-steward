// 找"点击执行器"：扫描 元素+0xd8 嵌入对象 的虚调用点 + 事件窗模块周边函数反编译
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;

public class EvtWin52 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(addr) + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, cap); i++) println(ls[i]);
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        decomp(0x141077710L, 60);
        decomp(0x141077720L, 60);
        decomp(0x141077730L, 100);
        decomp(0x141077c00L, 100);
        decomp(0x14107d780L, 90);
        decomp(0x141085090L, 80);

        // 扫描：MOV R?, [R? + 0xd8] 后 6 条内出现 CALL [R? + ..] —— 找点击/生命周期调用点
        println("==== scan: [reg+0xd8] deref then indirect call ====");
        int shown = 0;
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isExecute()) continue;
            long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
            if (hi < 0x141060000L || lo > 0x1410c0000L) continue;   // 事件窗口模块附近
            Instruction ins = currentProgram.getListing().getInstructionAt(b.getStart());
            if (ins == null) ins = currentProgram.getListing().getInstructionAfter(b.getStart());
            int guard = 0;
            while (ins != null && guard < 400000) {
                long off = ins.getAddress().getOffset();
                if (off > hi) break;
                String s = ins.toString();
                if (s.startsWith("MOV") && s.contains("qword ptr") && s.contains("+ 0xd8]")) {
                    // 看后续
                    Instruction n2 = ins.getNext();
                    StringBuilder chain = new StringBuilder(s);
                    boolean found = false;
                    for (int k = 0; k < 6 && n2 != null; k++) {
                        String s2 = n2.toString();
                        if (s2.startsWith("CALL qword ptr")) { found = true; chain.append(" ;; ").append(s2); break; }
                        n2 = n2.getNext();
                    }
                    if (found) {
                        Function f = getFunctionContaining(ins.getAddress());
                        println("  " + ins.getAddress() + "  " + chain + "   [" +
                                (f != null ? f.getName() + "@" + f.getEntryPoint() : "?") + "]");
                        if (++shown >= 40) { println("  (cap)"); return; }
                    }
                }
                ins = ins.getNext();
                guard++;
            }
        }
        println("==== done ====");
    }
}
