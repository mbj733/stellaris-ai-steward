// 找 option_click 分析函数的调用方（事件选项点击处理器），并找 CEventWindow 类 RTTI
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class ClickHandler extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== callers of FUN_1412913a0 (option_click analytics) ====");
        for (Reference r : getReferencesTo(toAddr(0x1412913a0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        int shown = 0;
        for (Reference r : getReferencesTo(toAddr(0x1412913a0L))) {
            if (shown >= 2) {
                break;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            if (f == null) {
                continue;
            }
            println("==== decompile caller " + f.getName() + " @" + f.getEntryPoint() + " chunk ====");
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                int start = 0;
                for (int i = 0; i < lines.length; i++) {
                    if (lines[i].contains("1412913a0")) {
                        start = Math.max(0, i - 30);
                        break;
                    }
                }
                for (int i = start; i < Math.min(lines.length, start + 70); i++) {
                    println("  " + lines[i]);
                }
            }
            shown++;
        }
        println("==== search string '.?AVCEventWindow@@' ====");
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            Object v = d.getValue();
            if (v instanceof String && ((String) v).startsWith(".?AVCEventWindow@@")) {
                println("  @ " + d.getAddress() + " : " + v);
            }
        }
        println("==== done ====");
    }
}
