// EvtWin4: human_ai 写点/读点上下文 + setter 调用者
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class EvtWin4 extends GhidraScript {

    void asmAt(long va, int before, int after) {
        println("==== asm @0x" + Long.toHexString(va) + " ====");
        Instruction ins = getInstructionAt(toAddr(va));
        if (ins == null) {
            for (long probe = va - 0x60; probe <= va; probe += 1) {
                ins = getInstructionAt(toAddr(probe));
                if (ins != null && ins.getAddress().getOffset() <= va && va <= ins.getMaxAddress().getOffset()) {
                    break;
                }
                ins = null;
            }
        }
        if (ins == null) {
            println("  (no instruction)");
            return;
        }
        for (int i = 0; i < before; i++) {
            Instruction p = ins.getPrevious();
            if (p == null) {
                break;
            }
            ins = p;
        }
        for (int i = 0; i < before + after; i++) {
            println("   " + ins.getAddress() + "  " + ins);
            ins = ins.getNext();
            if (ins == null) {
                break;
            }
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " (0x" + Long.toHexString(va) + ") ====");
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
        }
    }

    @Override
    public void run() throws Exception {
        asmAt(0x14014fd40L, 12, 26);   // human_ai 分支
        asmAt(0x140a99216L, 12, 16);   // 唯一读点上下文
        asmAt(0x14014e940L, 0, 26);    // 执行器入口
        allRefs(0x140959f10L, "setter writes human_ai (from checkbox)");
        allRefs(0x14095a070L, "setter2 writes human_ai");
        println("==== done ====");
    }
}
