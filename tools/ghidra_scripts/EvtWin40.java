// 崩溃定位：0x141aa5f80（04:12 crash offset）所在函数 + 现场汇编
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class EvtWin40 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long crash = 0x141aa5f80L;
        Function f = getFunctionContaining(toAddr(crash));
        println("==== crash 0x" + Long.toHexString(crash) + " 所在函数 ====");
        println(f != null ? ("  " + f.getName() + " @0x" + f.getEntryPoint()) : "  (无函数包含)");
        if (f != null) {
            DecompInterface di = new DecompInterface();
            di.openProgram(currentProgram);
            DecompileResults res = di.decompileFunction(f, 90, monitor);
            println("==== decompile (cap 90) ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, 90); i++) println("  " + ls[i]);
        }
        println("==== 现场汇编 ±0x40 ====");
        Address start = toAddr(crash - 0x40);
        Instruction ins = getInstructionAt(start);
        if (ins == null) ins = getInstructionAfter(start);
        int n = 0;
        while (ins != null && n < 60) {
            String tag = ins.getAddress().getOffset() == crash ? "   <<<< CRASH 偏移" : "";
            println("  " + ins.getAddress() + "   " + ins + tag);
            if (ins.getAddress().getOffset() > crash + 0x30) break;
            ins = ins.getNext();
            n++;
        }
        println("==== done ====");
    }
}
