// 查 "finish_research"/"research_technology"/"instant_build"/"survey" 的引用点，定位完整控制台指令表
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class CmdTable extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] strs = { 0x1423e5258L, 0x1423e53d8L, 0x1423e5b28L, 0x14232e780L, 0x14232c6d4L };
        for (long s : strs) {
            println("==== xrefs to 0x" + Long.toHexString(s) + " ====");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(s))) {
                if (n >= 6) {
                    break;
                }
                Function f = getFunctionContaining(r.getFromAddress());
                println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                        + "  in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
                n++;
            }
        }
        println("==== instrs around finish_research ref ====");
        Reference first = null;
        for (Reference r : getReferencesTo(toAddr(0x1423e5258L))) {
            first = r;
            break;
        }
        if (first != null) {
            long a = first.getFromAddress().getOffset();
            Instruction ins = getInstructionAt(toAddr(a - 0x30));
            if (ins == null) {
                ins = getInstructionAfter(toAddr(a - 0x30));
            }
            int m = 0;
            while (ins != null && m < 40 && ins.getAddress().getOffset() < a + 0x40) {
                println("  " + ins.getAddress() + "   " + ins.toString());
                ins = ins.getNext();
                m++;
            }
        }
        println("==== done ====");
    }
}
