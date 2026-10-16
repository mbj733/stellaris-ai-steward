// 追 CEventWindow::Setup 的 lambda：RTTI 字符串 -> vftable -> 点击处理函数
// 另：打印 14ecf0..14ee40（token 构造区）、14107a180 头 30 行
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class FindLambda extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== strings containing 'Setup@CEventWindow' ====");
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            Object v = d.getValue();
            if (v instanceof String && ((String) v).contains("Setup@CEventWindow")) {
                println("  @ " + d.getAddress() + " : " + v);
                for (Reference r : getReferencesTo(d.getAddress())) {
                    println("    ref from " + r.getFromAddress() + " (" + r.getReferenceType() + ")");
                }
            }
        }
        println("==== strings containing 'CEventWindow@@' ====");
        int cnt = 0;
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            Object v = d.getValue();
            if (v instanceof String && ((String) v).contains("CEventWindow@@") && cnt < 10) {
                println("  @ " + d.getAddress() + " : " + v);
                cnt++;
            }
        }
        println("==== instrs 14ecf0..14ee40 (token construction) ====");
        Instruction ins = getInstructionAt(toAddr(0x14014ecf0L));
        if (ins == null) {
            ins = getInstructionAfter(toAddr(0x14014ecf0L - 0x20));
        }
        int n = 0;
        while (ins != null && ins.getAddress().getOffset() < 0x14014ee40L && n < 90) {
            println("  " + ins.getAddress() + "   " + ins.toString());
            ins = ins.getNext();
            n++;
        }
        println("==== done ====");
    }
}
