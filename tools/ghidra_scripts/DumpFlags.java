// 反汇编 0x14014fa40..0x14014fb40: 弄清每个指令名对应的全局标志字节
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;

public class DumpFlags extends GhidraScript {
    @Override
    public void run() throws Exception {
        Instruction ins = getInstructionAt(toAddr(0x14014fa40L));
        if (ins == null) {
            ins = getInstructionAfter(toAddr(0x14014fa40L - 0x20));
        }
        println("==== instructions 14014fa40..14014fb40 ====");
        int n = 0;
        while (ins != null && ins.getAddress().getOffset() <= 0x14014fb40L && n < 120) {
            println("  " + ins.getAddress() + "   " + ins.toString());
            ins = ins.getNext();
            n++;
        }
        println("==== done ====");
    }
}
