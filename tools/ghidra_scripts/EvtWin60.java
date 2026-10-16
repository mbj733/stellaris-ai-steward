// AI 事件队列解剖：FUN_1402b9e80（入队） / FUN_14026c5d0（移除） + 容器消费方扫描
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import java.util.LinkedHashSet;

public class EvtWin60 extends GhidraScript {
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

    private void scanInstr(String disp, String label) {
        println("==== instr scan '" + disp + "' (" + label + ") ====");
        LinkedHashSet<String> fns = new LinkedHashSet<>();
        try {
            ghidra.program.model.listing.InstructionIterator it =
                currentProgram.getListing().getInstructions(true);
            int cnt = 0;
            while (it.hasNext() && cnt < 4000) {
                ghidra.program.model.listing.Instruction ins = it.next();
                String s = ins.toString();
                if (s.contains(disp)) {
                    cnt++;
                    if (cnt <= 25) {
                        Function f = getFunctionContaining(ins.getAddress());
                        println("  " + ins.getAddress() + "  " + s + "   ["
                                + (f != null ? f.getName() : "?") + "]");
                    }
                }
            }
            println("  合计 " + cnt + " 处");
        } catch (Exception e) { println("  fail: " + e); }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        xrefs(0x1402b9e80L, "FUN_1402b9e80(入队)");
        xrefs(0x14026c5d0L, "FUN_14026c5d0(移除)");
        decomp(0x1402b9e80L, 260);
        decomp(0x14026c5d0L, 200);
        scanInstr("+ 0x1c4]", "容器计数/相关");
        scanInstr("+ 0x1b0]", "容器本体");
        println("==== done EvtWin60 ====");
    }
}
