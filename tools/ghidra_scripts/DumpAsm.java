// 反汇编 0x14014fbc4（human_ai 引用点）周边 + 查 FUN_14014e940 的调用者
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class DumpAsm extends GhidraScript {
    @Override
    public void run() throws Exception {
        long target = 0x14014fbc4L;
        Address start = toAddr(target - 0x60);
        Instruction ins = getInstructionAt(start);
        if (ins == null) {
            ins = getInstructionAfter(start);
        }
        println("==== asm around 14014fbc4 ====");
        int n = 0;
        while (ins != null && n < 90) {
            println("  " + ins.getAddress() + "   " + ins.toString());
            if (ins.getAddress().getOffset() > target + 0x60) {
                break;
            }
            ins = ins.getNext();
            n++;
        }
        println("==== callers of FUN_14014e940 ====");
        for (Reference r : getReferencesTo(toAddr(0x14014e940L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + "   in "
                    + (f != null ? f.getName() + " @" + f.getEntryPoint() : "?"));
        }
        println("==== entry prologue FUN_14014e940 ====");
        Instruction e = getInstructionAt(toAddr(0x14014e940L));
        int m = 0;
        while (e != null && m < 40) {
            println("  " + e.getAddress() + "   " + e.toString());
            e = e.getNext();
            m++;
        }
        println("==== asm around 14014bcc2 (caller site) ====");
        long csite = 0x14014bcc2L;
        Instruction c = getInstructionAt(toAddr(csite - 0x50));
        if (c == null) {
            c = getInstructionAfter(toAddr(csite - 0x50));
        }
        int k = 0;
        while (c != null && k < 55) {
            println("  " + c.getAddress() + "   " + c.toString());
            if (c.getAddress().getOffset() > csite + 0x20) {
                break;
            }
            c = c.getNext();
            k++;
        }
        println("==== done ====");
    }
}
