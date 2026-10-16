// 查各"指令标志字节"的读取方 + 事件窗口 UI 字符串引用
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class FlagXrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] flags = { 0x142814839L, 0x14281483aL, 0x14281483bL, 0x14281485eL,
                         0x14311123aL, 0x143111235L, 0x14311123cL, 0x1431146f8L };
        for (long f : flags) {
            int total = 0;
            StringBuilder sb = new StringBuilder();
            for (Reference r : getReferencesTo(toAddr(f))) {
                total++;
                if (total <= 8) {
                    Function fx = getFunctionContaining(r.getFromAddress());
                    sb.append("\n    ").append(r.getReferenceType()).append(" from ")
                      .append(r.getFromAddress()).append(" in ")
                      .append(fx != null ? fx.getName() : "?");
                }
            }
            println("flag 0x" + Long.toHexString(f) + " : " + total + " refs" + sb.toString());
        }
        String[] names = { "event_window_option_entry", "event_option_button", "option_click" };
        for (String nm : names) {
            println("==== string '" + nm + "' ====");
            for (Data d : currentProgram.getListing().getDefinedData(true)) {
                Object v = d.getValue();
                if (v instanceof String && ((String) v).equals(nm)) {
                    println("  @ " + d.getAddress());
                    int n = 0;
                    for (Reference r : getReferencesTo(d.getAddress())) {
                        if (n >= 5) break;
                        Function fx = getFunctionContaining(r.getFromAddress());
                        println("    " + r.getReferenceType() + " from " + r.getFromAddress()
                                + " in " + (fx != null ? fx.getName() : "?"));
                        n++;
                    }
                }
            }
        }
        println("==== done ====");
    }
}
