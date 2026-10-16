// (a) FUN_1420666a0 调用 FUN_14014bab0 前的参数设置；(b) 0x14fb40~0x14fe00 剩余指令
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class DumpMore extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== instrs around call site 1420667cd ====");
        Instruction c = getInstructionAt(toAddr(0x142066780L));
        if (c == null) {
            c = getInstructionAfter(toAddr(0x142066780L));
        }
        int n = 0;
        while (c != null && c.getAddress().getOffset() < 0x142066800L && n < 70) {
            println("  " + c.getAddress() + "   " + c.toString());
            c = c.getNext();
            n++;
        }
        println("==== instrs 14fb40..14fe00 ====");
        Instruction ins = getInstructionAt(toAddr(0x14014fb40L));
        if (ins == null) {
            ins = getInstructionAfter(toAddr(0x14014fb40L - 0x20));
        }
        int m = 0;
        while (ins != null && ins.getAddress().getOffset() < 0x14014fe00L && m < 160) {
            String s = ins.toString();
            if (s.startsWith("LEA RDX") || s.startsWith("MOV RCX") || s.startsWith("JMP")
                    || s.startsWith("MOV byte") || s.startsWith("MOV dword") || s.startsWith("OR ")
                    || s.startsWith("CALL")) {
                println("  " + ins.getAddress() + "   " + s);
            }
            ins = ins.getNext();
            m++;
        }
        println("==== done ====");
    }
}
