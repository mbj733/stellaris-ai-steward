// 扫描 FUN_14014e940 中所有触达 R9/R15/R14 的指令，弄清 token 从哪来
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;

public class ScanRegs extends GhidraScript {
    @Override
    public void run() throws Exception {
        Instruction ins = getInstructionAt(toAddr(0x14014e940L));
        println("==== instructions touching R9/R15/R14 (14014e940..14014fc00) ====");
        while (ins != null && ins.getAddress().getOffset() < 0x14014fc00L) {
            String s = ins.toString();
            if (s.contains("R9") || s.contains("R15") || s.contains("R14")) {
                println("  " + ins.getAddress() + "   " + s);
            }
            ins = ins.getNext();
        }
        println("==== done ====");
    }
}
