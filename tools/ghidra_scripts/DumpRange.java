// 反汇编 0x14014fb40~0x14014fb80（debugtooltip 分支）+ 查两个全局标志的引用点
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class DumpRange extends GhidraScript {
    @Override
    public void run() throws Exception {
        long startA = 0x14014fb38L;
        long endA = 0x14014fb80L;
        Instruction ins = getInstructionAt(toAddr(startA));
        if (ins == null) {
            ins = getInstructionAfter(toAddr(startA));
        }
        println("==== instructions 14014fb38..14014fb80 ====");
        int n = 0;
        while (ins != null && ins.getAddress().getOffset() <= endA && n < 60) {
            println("  " + ins.getAddress() + "   " + ins.toString());
            ins = ins.getNext();
            n++;
        }
        long[] globals = { 0x1431146f9L, 0x14281485eL };
        for (long g : globals) {
            println("==== xrefs to 0x" + Long.toHexString(g) + " ====");
            for (Reference r : getReferencesTo(toAddr(g))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  " + r.getReferenceType() + "  from " + r.getFromAddress()
                        + "  in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        }
        println("==== entry head 14014e940..+0x1C0 ====");
        Instruction e = getInstructionAt(toAddr(0x14014e940L));
        int m = 0;
        while (e != null && m < 100) {
            println("  " + e.getAddress() + "   " + e.toString());
            if (e.getAddress().getOffset() > 0x14014e940L + 0x1C0) {
                break;
            }
            e = e.getNext();
            m++;
        }
        println("==== done ====");
    }
}
