// 反编译 FUN_14014bab0 与 0x141b0f910，弄清控制台调用的参数契约
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class DecompFn extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        Function f1 = getFunctionContaining(toAddr(0x14014bab0L));
        if (f1 != null) {
            println("==== FUN_14014bab0 decompiled ====");
            DecompileResults r = dec.decompileFunction(f1, 120, monitor);
            if (r != null && r.decompileCompleted()) {
                String[] lines = r.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 150); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        Function f2 = getFunctionContaining(toAddr(0x141b0f910L));
        if (f2 != null) {
            println("==== " + f2.getName() + " decompiled head ====");
            DecompileResults r2 = dec.decompileFunction(f2, 120, monitor);
            if (r2 != null && r2.decompileCompleted()) {
                String[] lines = r2.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 80); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        println("==== done ====");
    }
}
