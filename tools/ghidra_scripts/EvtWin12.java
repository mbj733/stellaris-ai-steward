// EvtWin12: 切分器 worker FUN_14015acf0 + 相关字符串工具
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class EvtWin12 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 150, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x14015acf0L, 150);   // split worker
        decompileFn(0x14015ace0L, 90);    // 近邻
        decompileFn(0x14015baa0L, 70);    // 字符串对象构造（游戏里常用）
        println("==== done ====");
    }
}
