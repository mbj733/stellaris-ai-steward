// FUN_14014bab0 的入口与调用者：判断它是否接收原始命令字符串
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class DumpCaller extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== prologue FUN_14014bab0 ====");
        Instruction ins = getInstructionAt(toAddr(0x14014bab0L));
        int n = 0;
        while (ins != null && n < 45) {
            println("  " + ins.getAddress() + "   " + ins.toString());
            ins = ins.getNext();
            n++;
        }
        println("==== callers of FUN_14014bab0 ====");
        for (Reference r : getReferencesTo(toAddr(0x14014bab0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + "   in "
                    + (f != null ? f.getName() + " @" + f.getEntryPoint() : "?"));
        }
        println("==== string args near 0x14014bab0: check what RDX/RCX set before 0x14014bcc2 ====");
        Instruction c = getInstructionAt(toAddr(0x14014bc70L));
        int m = 0;
        while (c != null && m < 40) {
            println("  " + c.getAddress() + "   " + c.toString());
            c = c.getNext();
            m++;
        }
        println("==== done ====");
    }
}
