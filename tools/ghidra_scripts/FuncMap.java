// 定位 0x14014e940 / 0x14014ec78 / 0x14014fa3f 各自属于哪个函数，并打印其入口
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class FuncMap extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] probes = { 0x14014e940L, 0x14014ec78L, 0x14014fa3fL, 0x14014fb38L, 0x14014bcc2L };
        for (long p : probes) {
            Function f = getFunctionContaining(toAddr(p));
            println("addr 0x" + Long.toHexString(p) + "  ->  "
                    + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "(不在任何函数内)"));
        }
        Function f2 = getFunctionContaining(toAddr(0x14014fa3fL));
        if (f2 != null) {
            println("==== head of dispatcher function " + f2.getName() + " ====");
            Instruction ins = getInstructionAt(f2.getEntryPoint());
            int n = 0;
            while (ins != null && n < 110) {
                println("  " + ins.getAddress() + "   " + ins.toString());
                ins = ins.getNext();
                n++;
            }
        }
        println("==== done ====");
    }
}
