// EvtWin22: 扫描菜单定义区域（0x1423a9400..0x1423aa800）的全部引用，找消费者/构建者
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin22 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long start = 0x1423a9400L;
        long end = 0x1423aa800L;
        int n = 0;
        for (long a = start; a < end; a += 4) {
            for (Reference r : getReferencesTo(toAddr(a))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  ref " + r.getReferenceType() + " to 0x" + Long.toHexString(a)
                        + " from " + r.getFromAddress()
                        + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
                if (++n >= 40) {
                    println("  ...(capped at 40)");
                    return;
                }
            }
        }
        println("total refs found: " + n);
        println("==== done ====");
    }
}
