// 查 FUN_1420666a0 的调用方（判断是否存在"每帧处理的指令队列"，若有则优先走纯内存写入）
// 另反编译其头部，确认 token 来源
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class QueueCheck extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== callers of FUN_1420666a0 ====");
        for (Reference r : getReferencesTo(toAddr(0x1420666a0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        Function f = getFunctionContaining(toAddr(0x1420666a0L));
        if (f != null) {
            println("==== decompile FUN_1420666a0 head ====");
            DecompileResults res = dec.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 90); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        println("==== done ====");
    }
}
