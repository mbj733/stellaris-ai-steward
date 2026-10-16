// EvtWin24: 找"调试菜单显示路径"——菜单控件族函数的调用者
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin24 extends GhidraScript {
    void refs(long va, String tag) {
        Function f0 = getFunctionContaining(toAddr(va));
        println("==== callers of " + tag + " (0x" + Long.toHexString(va) + ", "
                + (f0 != null ? f0.getName() : "?") + ") ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (++n >= 10) {
                println("  ...");
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        refs(0x140a98c80L, "menu build fn");
        refs(0x140a8dd70L, "widget fn1");
        refs(0x140a92f70L, "widget fn2");
        refs(0x140a93870L, "widget fn3");
        println("==== done ====");
    }
}
