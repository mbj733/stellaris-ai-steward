// 追 CEventWindow::Setup 的 lambda RTTI -> vftable -> 构造点；再反编译事件窗口两个 GUI 函数
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class LambdaTrace extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== refs to lambda RTTI 0x1428c59b0 ====");
        for (Reference r : getReferencesTo(toAddr(0x1428c59b0L))) {
            println("  " + r.getReferenceType() + " from " + r.getFromAddress());
        }
        println("==== refs to bind_t RTTI 0x1428c59f0 ====");
        for (Reference r : getReferencesTo(toAddr(0x1428c59f0L))) {
            println("  " + r.getReferenceType() + " from " + r.getFromAddress());
        }
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        String[] fns = { "0x14107a180", "0x1410793a0", "0x1412913a0" };
        for (String fs : fns) {
            long a = Long.decode(fs);
            Function f = getFunctionContaining(toAddr(a));
            if (f == null) {
                continue;
            }
            println("==== decompile " + fs + " (" + f.getName() + ") head ====");
            DecompileResults res = dec.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 100); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        println("==== done ====");
    }
}
