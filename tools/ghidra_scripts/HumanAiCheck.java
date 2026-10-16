// 确认 human_ai 标志 0x142814839 的全部引用（读/写方）+ 反编译读取它的主函数
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class HumanAiCheck extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== all refs to 0x142814839 (human_ai flag) ====");
        for (Reference r : getReferencesTo(toAddr(0x142814839L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  [" + r.getReferenceType() + "] from " + r.getFromAddress()
                    + "  in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        println("==== all refs to 0x14281483a (berserk_ai) ====");
        for (Reference r : getReferencesTo(toAddr(0x14281483aL))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  [" + r.getReferenceType() + "] from " + r.getFromAddress()
                    + "  in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        for (long a : new long[] { 0x140a98c80L }) {
            Function f = getFunctionContaining(toAddr(a));
            if (f == null) {
                continue;
            }
            println("==== decompile " + f.getName() + " full (first 140 lines) ====");
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 140); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        println("==== done ====");
    }
}
