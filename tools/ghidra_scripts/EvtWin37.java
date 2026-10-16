// 事件选项链：FUN_1408e5d20 各调用点现场（确认 pos 参数与 ctx 来源；看调用后如何消费命令对象）
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;

public class EvtWin37 extends GhidraScript {

    private void asmAround(long target, int back, int fwd) throws Exception {
        Address start = toAddr(target - back);
        Instruction ins = getInstructionAt(start);
        if (ins == null) ins = getInstructionAfter(start);
        println("==== asm around 0x" + Long.toHexString(target) + " ====");
        int n = 0;
        while (ins != null && n < 80) {
            String tag = "";
            long off = ins.getAddress().getOffset();
            if (off == target) tag = "   <<<< TARGET";
            println("  " + ins.getAddress() + "   " + ins + tag);
            if (off > target + fwd) break;
            ins = ins.getNext();
            n++;
        }
    }

    @Override
    public void run() throws Exception {
        // FUN_1403f5de0（事件内核，AI 路径）里 4 处对 FUN_1408e5d20 的调用
        asmAround(0x1403f6a7fL, 0x60, 0x30);
        asmAround(0x1403f6aeeL, 0x50, 0x50);
        asmAround(0x1403f6b57L, 0x50, 0x50);
        asmAround(0x1403f6d0aL, 0x60, 0x40);
        // FUN_141146a90 的调用点
        asmAround(0x141146c79L, 0x60, 0x50);
        // 分发器里的调用点
        asmAround(0x14107b6e1L, 0x40, 0x30);
        println("==== done ====");
    }
}
