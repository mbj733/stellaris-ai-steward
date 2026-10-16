// EvtWin26: 事件窗口日志字符串 → 引用它们的处理函数（选项/关闭逻辑）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;
import java.util.Set;

public class EvtWin26 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
            }
            dec.dispose();
        } catch (Exception e) {
        }
    }

    @Override
    public void run() throws Exception {
        String[] needles = {"event_dismiss", "event_close", "coop_event_option_selected", "DEBUG: Event ID", "coop_current_event_option"};
        Set<Long> fnAddrs = new LinkedHashSet<>();
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            Object v = d.getValue();
            if (!(v instanceof String)) {
                continue;
            }
            String s = (String) v;
            for (String n : needles) {
                if (s.contains(n)) {
                    println("字符串 @0x" + Long.toHexString(d.getAddress().getOffset()) + " : " + s.substring(0, Math.min(60, s.length())));
                    for (Reference r : getReferencesTo(d.getAddress())) {
                        Function f = getFunctionContaining(r.getFromAddress());
                        println("   ref from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                                + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
                        if (f != null) {
                            fnAddrs.add(f.getEntryPoint().getOffset());
                        }
                    }
                    break;
                }
            }
        }
        int n = 0;
        for (long fe : fnAddrs) {
            if (n++ >= 4) {
                break;
            }
            decompileFn(fe, 90);
        }
        println("==== done ====");
    }
}
