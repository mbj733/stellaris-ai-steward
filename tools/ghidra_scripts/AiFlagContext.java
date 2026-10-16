// human_ai 标志的三个写入点上下文 + 读取点上下文，判断开/关语义
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;

public class AiFlagContext extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] sites = { 0x140959f14L, 0x14095a074L };
        for (long s : sites) {
            println("==== around 0x" + Long.toHexString(s) + " ====");
            Instruction ins = getInstructionAt(toAddr(s - 0x40));
            if (ins == null) {
                ins = getInstructionAfter(toAddr(s - 0x40));
            }
            int n = 0;
            while (ins != null && n < 50 && ins.getAddress().getOffset() < s + 0x30) {
                println("  " + ins.getAddress() + "   " + ins.toString());
                ins = ins.getNext();
                n++;
            }
        }
        println("==== around read 0x140a99216 ====");
        Instruction ins2 = getInstructionAt(toAddr(0x140a991e0L));
        if (ins2 == null) {
            ins2 = getInstructionAfter(toAddr(0x140a991e0L));
        }
        int m = 0;
        while (ins2 != null && m < 40 && ins2.getAddress().getOffset() < 0x140a99260L) {
            println("  " + ins2.getAddress() + "   " + ins2.toString());
            ins2 = ins2.getNext();
            m++;
        }
        println("==== done ====");
    }
}
