// 全文反编译：窗口命令分发器 FUN_14107b1d0（读全部分支，找"选中执行"路径）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class EvtWin47 extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (long addr : new long[] { 0x14107b1d0L }) {
            Function f = getFunctionAt(toAddr(addr));
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            println("==== " + f.getName() + " 全文 ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (String l : ls) println(l);
        }
        println("==== done ====");
    }
}
