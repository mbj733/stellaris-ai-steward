// 找"真点击路径"：扫描窗口特征字段位移的引用 + UI管理器全局引用 + B对象 vtable 引用
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

public class EvtWin50 extends GhidraScript {

    private void refs(long addr, String tag) {
        println("==== refs to " + tag + " 0x" + Long.toHexString(addr) + " ====");
        for (Reference r : getReferencesTo(toAddr(addr))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
    }

    private void scanDisp(String needle) {
        println("==== instr scan: displacement '" + needle + "' ====");
        int n = 0;
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isExecute()) continue;
            long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
            Instruction ins = currentProgram.getListing().getInstructionAt(b.getStart());
            if (ins == null) ins = currentProgram.getListing().getInstructionAfter(b.getStart());
            int guard = 0;
            while (ins != null && guard < 4000000) {
                long off = ins.getAddress().getOffset();
                if (off > hi) break;
                String s = ins.toString();
                if (s.contains(needle)) {
                    Function f = getFunctionContaining(ins.getAddress());
                    println("  " + ins.getAddress() + "  " + s + "   [" +
                            (f != null ? f.getName() + "@" + f.getEntryPoint() : "?") + "]");
                    if (++n >= 80) { println("  (cap 80)"); return; }
                }
                ins = ins.getNext();
                guard++;
            }
        }
    }

    @Override
    public void run() throws Exception {
        refs(0x143159458L, "UI mgr global");
        refs(0x14257CEB0L, "B vtable");
        scanDisp("+ 0x9e4]");
        scanDisp("+ 0x9a0]");
        scanDisp("+ 0x2228]");
        scanDisp("+ 0x2250]");
        println("==== done ====");
    }
}
